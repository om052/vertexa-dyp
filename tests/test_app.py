import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.services.buddy_provider import GeminiProvider


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(self.database_path),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_directory.cleanup()

    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_homepage_loads_frontend_assets(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CodeQuest AI", response.data)
        self.assertIn(b"Check service", response.data)

    def test_startup_does_not_create_database_or_run_migrations(self):
        self.client.get("/")

        self.assertFalse(self.database_path.exists())

    def test_buddy_provider_defaults_to_mock(self):
        self.assertEqual(self.app.config["BUDDY_PROVIDER"], "mock")
        self.assertEqual(
            self.app.extensions["buddy_provider"].provider_name,
            "deterministic-local-mock",
        )

    def test_gemini_provider_is_selected_only_when_explicitly_configured(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE_PATH": str(self.database_path),
                    "BUDDY_PROVIDER": "gemini",
                    "BUDDY_GEMINI_ADULTS_ONLY": True,
                    "BUDDY_GEMINI_FREE_TIER_CONFIRMED": True,
                }
            )
        self.assertIsInstance(app.extensions["buddy_provider"], GeminiProvider)
        self.assertTrue(app.extensions["buddy_provider"].is_available)
        self.assertNotIn("GEMINI_API_KEY", app.config)
        with app.app_context():
            db.engine.dispose()

    def test_gemini_without_key_starts_unavailable_without_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            app = create_app(
                {
                    "TESTING": True,
                    "DATABASE_PATH": str(self.database_path),
                    "BUDDY_PROVIDER": "gemini",
                    "BUDDY_GEMINI_ADULTS_ONLY": True,
                    "BUDDY_GEMINI_FREE_TIER_CONFIRMED": True,
                }
            )
        provider = app.extensions["buddy_provider"]
        self.assertIsInstance(provider, GeminiProvider)
        self.assertFalse(provider.is_available)
        self.assertFalse(provider.is_mock)
        with app.app_context():
            db.engine.dispose()

    def test_startup_rejects_unsupported_buddy_provider(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "BUDDY_PROVIDER must be set to 'mock' or 'gemini'",
        ):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE_PATH": str(self.database_path),
                    "BUDDY_PROVIDER": "unsupported",
                }
            )

    def test_production_requires_secret_key(self):
        with patch.dict(
            os.environ,
            {"CODEQUEST_ENV": "production"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "CODEQUEST_SECRET_KEY must be set"
            ):
                create_app()

    def test_production_accepts_secret_key_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "CODEQUEST_ENV": "production",
                "CODEQUEST_SECRET_KEY": "test-only-secret",
                "CODEQUEST_DATABASE_PATH": str(self.database_path),
            },
            clear=True,
        ):
            app = create_app({"TESTING": True})

        self.assertEqual(app.config["ENVIRONMENT"], "production")
        self.assertEqual(app.config["SECRET_KEY"], "test-only-secret")
        with app.app_context():
            db.engine.dispose()

    def test_production_requires_explicit_absolute_database_path(self):
        with patch.dict(
            os.environ,
            {
                "CODEQUEST_ENV": "production",
                "CODEQUEST_SECRET_KEY": "test-only-secret",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "CODEQUEST_DATABASE_PATH must be an absolute path"
            ):
                create_app()

    def test_production_rejects_relative_database_path(self):
        with patch.dict(
            os.environ,
            {
                "CODEQUEST_ENV": "production",
                "CODEQUEST_SECRET_KEY": "test-only-secret",
                "CODEQUEST_DATABASE_PATH": "instance/codequest.sqlite3",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "CODEQUEST_DATABASE_PATH must be an absolute path"
            ):
                create_app()


if __name__ == "__main__":
    unittest.main()
