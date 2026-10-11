import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models import Language, Lesson, Topic, User
from app.services.curriculum import seed_curriculum


class LearningPagesTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "pages.sqlite3"
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

    def seed(self):
        with self.app.app_context():
            return seed_curriculum()

    def test_home_and_learn_render_helpful_empty_states_without_seeding(self):
        for path in ("/", "/learn"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Loading learning paths", response.data)
        with self.app.app_context():
            self.assertEqual(db.session.scalar(select(func.count()).select_from(Language)), 0)
            self.assertEqual(db.session.scalar(select(func.count()).select_from(Topic)), 0)
            self.assertEqual(db.session.scalar(select(func.count()).select_from(Lesson)), 0)

    def test_liveness_and_homepage_remain_available(self):
        self.assertIn(b"CodeQuest", self.client.get("/").data)
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_buddy_page_requires_login_and_renders_for_authenticated_user(self):
        response = self.client.get("/buddy")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        client = self.app.test_client()
        with client.session_transaction() as state:
            state["user_id"] = user_id
        response = client.get("/buddy")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"MOCK MODE", response.data)
        self.assertIn(b"responses are simulated", response.data)
        self.assertIn(b"Real AI is not connected", response.data)
        self.assertIn(b"messages are not sent to an AI provider", response.data)
        self.assertIn(b'name="csrf-token" content="', response.data)
        self.assertIn(b'id="buddy-history-enable"', response.data)
        self.assertIn(b'id="buddy-memory-toggle"', response.data)

    def test_buddy_page_loads_its_static_assets(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        client = self.app.test_client()
        with client.session_transaction() as state:
            state["user_id"] = user_id
        page = client.get("/buddy")
        self.assertEqual(page.status_code, 200)

        script = client.get("/static/js/buddy.js")
        styles = client.get("/static/css/styles.css")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"submitMessage", script.data)
        self.assertNotIn(b"innerHTML", script.data)
        self.assertEqual(styles.status_code, 200)
        self.assertIn(b"@media (max-width: 375px)", styles.data)
        script.close()
        styles.close()

    def test_learning_pages_render_for_seeded_catalog_items(self):
        self.seed()
        paths = (
            "/learn",
            "/learn/python",
            "/learn/python/topics/getting-started",
            "/learn/python/topics/getting-started/lessons/getting-started",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"CodeQuest", response.data)

    def test_unknown_language_topic_or_lesson_returns_html_not_found(self):
        paths = (
            "/learn/not-a-language",
            "/learn/python/topics/not-a-topic",
            "/learn/python/topics/getting-started/lessons/not-a-lesson",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertIn(b"This path isn't on the map", response.data)

    def test_language_api_counts_match_catalog(self):
        self.seed()
        response = self.client.get("/api/languages")
        self.assertEqual(response.status_code, 200)
        languages = response.get_json()["languages"]
        self.assertEqual(len(languages), 4)
        self.assertTrue(all(language["topic_count"] == 10 for language in languages))
        self.assertTrue(all(language["lesson_count"] == 10 for language in languages))

    def test_roadmap_and_topic_api_counts_are_consistent(self):
        self.seed()
        roadmap = self.client.get("/api/languages/python").get_json()["language"]
        self.assertEqual((roadmap["topic_count"], roadmap["lesson_count"]), (10, 10))
        self.assertTrue(all(topic["lesson_count"] == 1 for topic in roadmap["topics"]))
        topic = self.client.get(
            "/api/languages/python/topics/getting-started"
        ).get_json()["topic"]
        self.assertEqual(topic["title"], "Getting started")
        self.assertEqual(len(topic["lessons"]), 1)

    def test_page_visits_do_not_mutate_existing_catalog(self):
        self.seed()
        before = self.catalog_counts()
        for path in (
            "/",
            "/learn",
            "/learn/python",
            "/learn/python/topics/getting-started",
            "/learn/python/topics/getting-started/lessons/getting-started",
        ):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.catalog_counts(), before)

    def catalog_counts(self):
        with self.app.app_context():
            return tuple(
                db.session.scalar(select(func.count()).select_from(model))
                for model in (Language, Topic, Lesson)
            )


if __name__ == "__main__":
    unittest.main()
