import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash

from app import create_app
from app.extensions import db
from app.models import LearnerProfile, User


CSRF_PATTERN = re.compile(rb'name="csrf_token" value="([^"]+)"')


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "auth.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(self.database_path),
            }
        )
        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_directory.cleanup()

    def token(self, client, path):
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        match = CSRF_PATTERN.search(response.data)
        self.assertIsNotNone(match, f"{path} did not include a CSRF token")
        return match.group(1).decode()

    def register(self, client=None, **overrides):
        client = client or self.client
        fields = {
            "username": "sample_learner",
            "email": "Learner@example.com",
            "password": "correct horse battery staple",
            "confirm_password": "correct horse battery staple",
        }
        fields.update(overrides)
        fields["csrf_token"] = self.token(client, "/auth/register")
        return client.post("/auth/register", data=fields)

    def login(self, client=None, identifier="sample_learner", password="correct horse battery staple", next_url=None):
        client = client or self.client
        fields = {
            "csrf_token": self.token(client, "/auth/login"),
            "identifier": identifier,
            "password": password,
        }
        if next_url is not None:
            fields["next"] = next_url
        return client.post("/auth/login", data=fields)

    def test_registration_creates_hash_and_exactly_one_profile_without_login(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/login")
        with self.app.app_context():
            user = db.session.scalar(select(User).where(User.username == "sample_learner"))
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password_hash, "correct horse battery staple")
            self.assertTrue(
                check_password_hash(
                    user.password_hash,
                    "correct horse battery staple",
                )
            )
            self.assertEqual(
                db.session.scalar(
                    select(func.count())
                    .select_from(LearnerProfile)
                    .where(LearnerProfile.user_id == user.id)
                ),
                1,
            )
        profile_response = self.client.get("/account/profile")
        self.assertEqual(profile_response.status_code, 302)
        self.assertIn("/auth/login", profile_response.headers["Location"])

    def test_registration_normalizes_username_and_email(self):
        response = self.register(
            username="  Sample_Learner  ",
            email="  LEARNER@EXAMPLE.COM ",
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = db.session.scalar(select(User))
            self.assertEqual(user.username, "sample_learner")
            self.assertEqual(user.email, "learner@example.com")

    def test_registration_rejects_invalid_fields_and_password_mismatch(self):
        cases = (
            {"username": "x"},
            {"username": "bad-name"},
            {"email": "not-an-email"},
            {"password": "short", "confirm_password": "short"},
            {"confirm_password": "different password"},
        )
        for values in cases:
            with self.subTest(values=values):
                response = self.register(**values)
                self.assertEqual(response.status_code, 400)
                self.assertIn(b"Please check the highlighted fields", response.data)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(select(func.count()).select_from(User)), 0)

    def test_registration_rejects_duplicate_username_and_email_case_insensitively(self):
        self.assertEqual(self.register().status_code, 302)
        duplicate_username = self.register(
            username="SAMPLE_LEARNER",
            email="another@example.com",
        )
        self.assertEqual(duplicate_username.status_code, 400)
        self.assertIn(b"username is already in use", duplicate_username.data)
        duplicate_email = self.register(
            username="another_learner",
            email="LEARNER@EXAMPLE.COM",
        )
        self.assertEqual(duplicate_email.status_code, 400)
        self.assertIn(b"email address is already in use", duplicate_email.data)

    def test_database_enforces_account_uniqueness(self):
        self.register()
        with self.app.app_context():
            with self.subTest(field="username"):
                db.session.add(
                    User(
                        username="sample_learner",
                        email="different@example.com",
                        password_hash="hash",
                    )
                )
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

            with self.subTest(field="email"):
                db.session.add(
                    User(
                        username="different_learner",
                        email="learner@example.com",
                        password_hash="hash",
                    )
                )
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_login_accepts_username_or_email_and_rotates_cookie_session(self):
        self.register()
        old_cookie = self.client.get_cookie(self.app.config["SESSION_COOKIE_NAME"])
        with self.client.session_transaction() as state:
            state["pre_auth_marker"] = "must be removed"
        before_login = self.client.get_cookie(self.app.config["SESSION_COOKIE_NAME"])

        response = self.login(identifier="LEARNER@EXAMPLE.COM")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")
        after_login = self.client.get_cookie(self.app.config["SESSION_COOKIE_NAME"])
        self.assertNotEqual(before_login.value, after_login.value)
        self.assertNotEqual(old_cookie.value, after_login.value)
        with self.client.session_transaction() as state:
            self.assertIn("user_id", state)
            self.assertNotIn("pre_auth_marker", state)
            self.assertNotIn("password", state)
            self.assertNotIn("email", state)
            self.assertNotIn("username", state)
            self.assertTrue(state.permanent)

    def test_invalid_login_returns_same_generic_message_for_unknown_and_wrong_password(self):
        self.register()
        unknown = self.login(identifier="nobody@example.com", password="wrong password")
        wrong = self.login(identifier="sample_learner", password="wrong password")
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        message = b"The username/email or password is incorrect."
        self.assertIn(message, unknown.data)
        self.assertIn(message, wrong.data)

    def test_login_rejects_legacy_user_without_credentials(self):
        with self.app.app_context():
            legacy_user = User(
                username="legacy_learner",
                email="legacy@example.com",
            )
            db.session.add(legacy_user)
            db.session.commit()
        response = self.login(
            identifier="legacy_learner",
            password="anything at all",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"The username/email or password is incorrect.", response.data)

    def test_malformed_stored_hash_fails_closed(self):
        self.register()
        with self.app.app_context():
            user = db.session.scalar(select(User))
            user.password_hash = "not-a-supported-password-hash"
            db.session.commit()
        response = self.login()
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_csrf_and_invalidates_session(self):
        self.register()
        self.login()
        response = self.client.post("/auth/logout")
        self.assertEqual(response.status_code, 400)
        token = self.token(self.client, "/account/settings")
        response = self.client.post(
            "/auth/logout",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/login")
        self.assertEqual(self.client.get("/account/profile").status_code, 302)

    def test_protected_profile_and_settings_redirect_anonymous_visitors(self):
        for path in ("/account/profile", "/account/settings"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].startswith("/auth/login?"))

    def test_authenticated_profile_and_settings_show_only_own_account(self):
        self.register()
        self.login()
        profile = self.client.get("/account/profile")
        settings = self.client.get("/account/settings")
        self.assertEqual(profile.status_code, 200)
        self.assertIn(b"@sample_learner", profile.data)
        self.assertIn(b"learner@example.com", profile.data)
        self.assertIn(b"Log out", profile.data)
        self.assertIn(b"Settings", profile.data)
        self.assertEqual(settings.status_code, 200)
        self.assertNotIn(b"correct horse battery staple", settings.data)

    def test_profile_settings_update_only_authenticated_user(self):
        self.register()
        self.login()
        self.register(
            self.app.test_client(),
            username="another_learner",
            email="another@example.com",
        )
        with self.app.app_context():
            other_user = db.session.scalar(
                select(User).where(User.username == "another_learner")
            )
            other_id = other_user.id

        token = self.token(self.client, "/account/settings")
        response = self.client.post(
            "/account/settings",
            data={
                "csrf_token": token,
                "display_name": "A learner",
                "bio": "<script>alert('x')</script>",
                "preferred_language_code": "",
                "user_id": other_id,
            },
        )
        self.assertEqual(response.status_code, 302)
        profile = self.client.get("/account/profile")
        self.assertIn(b"A learner", profile.data)
        self.assertIn(b"&lt;script&gt;", profile.data)
        with self.app.app_context():
            my_user = db.session.scalar(
                select(User).where(User.username == "sample_learner")
            )
            other_profile = db.session.get(LearnerProfile, other_id)
            self.assertEqual(my_user.profile.display_name, "A learner")
            self.assertEqual(my_user.profile.bio, "<script>alert('x')</script>")
            self.assertIsNone(other_profile.display_name)

    def test_profile_form_rejects_invalid_values_without_mutation(self):
        self.register()
        self.login()
        token = self.token(self.client, "/account/settings")
        response = self.client.post(
            "/account/settings",
            data={
                "csrf_token": token,
                "display_name": "x" * 81,
                "bio": "",
                "preferred_language_code": "missing-language",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Display name must be 80 characters or fewer", response.data)
        self.assertIn(b"Choose a language from the available list", response.data)
        with self.app.app_context():
            user = db.session.scalar(select(User))
            self.assertIsNone(user.profile.display_name)

    def test_state_changing_account_forms_require_csrf(self):
        response = self.client.post(
            "/auth/register",
            data={
                "username": "sample_learner",
                "email": "learner@example.com",
                "password": "correct horse battery staple",
                "confirm_password": "correct horse battery staple",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.register()
        login_response = self.client.post(
            "/auth/login",
            data={
                "identifier": "sample_learner",
                "password": "correct horse battery staple",
            },
        )
        self.assertEqual(login_response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(select(func.count()).select_from(User)), 1)

    def test_profile_update_requires_csrf_and_logout_is_post_only(self):
        self.register()
        self.login()
        response = self.client.post(
            "/account/settings",
            data={
                "display_name": "Forged change",
                "bio": "",
                "preferred_language_code": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/auth/logout").status_code, 405)
        with self.app.app_context():
            user = db.session.scalar(select(User))
            self.assertIsNone(user.profile.display_name)

    def test_external_and_protocol_relative_next_urls_are_rejected(self):
        self.register()
        for unsafe_next in (
            "https://attacker.example/path",
            "//attacker.example/path",
            "/%2f%2fattacker.example/path",
            "/%5c%5cattacker.example/path",
        ):
            with self.subTest(next=unsafe_next):
                response = self.login(next_url=unsafe_next)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/")
                self.client.post(
                    "/auth/logout",
                    data={"csrf_token": self.token(self.client, "/auth/login")},
                )

    def test_safe_internal_next_url_is_preserved(self):
        self.register()
        response = self.login(next_url="/learn?from=login")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/learn?from=login")

    def test_production_session_cookie_settings_are_secure(self):
        with patch.dict(
            "os.environ",
            {
                "CODEQUEST_ENV": "production",
                "CODEQUEST_SECRET_KEY": "test-only-secret",
                "CODEQUEST_DATABASE_PATH": str(self.database_path),
            },
            clear=True,
        ):
            production_app = create_app({"TESTING": True})
        self.assertTrue(production_app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(production_app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(production_app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        with production_app.app_context():
            db.engine.dispose()

    def test_missing_learner_profile_is_handled_and_recreated_once_on_save(self):
        self.register()
        self.login()
        with self.app.app_context():
            user = db.session.scalar(select(User))
            user_id = user.id
            db.session.delete(user.profile)
            db.session.commit()
        self.assertEqual(self.client.get("/account/profile").status_code, 200)
        token = self.token(self.client, "/account/settings")
        response = self.client.post(
            "/account/settings",
            data={
                "csrf_token": token,
                "display_name": "Restored profile",
                "bio": "",
                "preferred_language_code": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(
                db.session.scalar(
                    select(func.count())
                    .select_from(LearnerProfile)
                    .where(LearnerProfile.user_id == user_id)
                ),
                1,
            )

    def test_stale_or_invalid_session_is_cleared_before_protected_access(self):
        with self.client.session_transaction() as state:
            state["user_id"] = "deleted-account"
            state["unrelated"] = "clear with stale identity"
        response = self.client.get("/account/profile")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])
        with self.client.session_transaction() as state:
            self.assertNotIn("user_id", state)
            self.assertNotIn("unrelated", state)

    def test_migration_preserves_existing_user_and_profile_rows(self):
        previous_revision = self.app.test_cli_runner().invoke(
            args=["db", "upgrade", "ce39ebd9f6d8"]
        )
        self.assertEqual(previous_revision.exit_code, 0, previous_revision.output)
        with self.app.app_context():
            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users (id, created_at, updated_at) "
                        "VALUES (:id, :created, :updated)"
                    ),
                    {
                        "id": "legacy-user",
                        "created": "2026-01-01 00:00:00",
                        "updated": "2026-01-01 00:00:00",
                    },
                )
                connection.execute(
                    text(
                        "INSERT INTO learner_profiles "
                        "(user_id, display_name, preferred_language_code, "
                        "created_at, updated_at) "
                        "VALUES (:id, :name, NULL, :created, :updated)"
                    ),
                    {
                        "id": "legacy-user",
                        "name": "Legacy learner",
                        "created": "2026-01-01 00:00:00",
                        "updated": "2026-01-01 00:00:00",
                    },
                )
        upgraded = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(upgraded.exit_code, 0, upgraded.output)
        with self.app.app_context():
            user = db.session.get(User, "legacy-user")
            profile = db.session.get(LearnerProfile, "legacy-user")
            self.assertIsNotNone(user)
            self.assertEqual(profile.display_name, "Legacy learner")
            self.assertIsNone(user.username)
            self.assertIsNone(user.email)
            self.assertIsNone(user.password_hash)
            self.assertIsNone(profile.bio)


if __name__ == "__main__":
    unittest.main()
