import tempfile
import unittest
import re
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import User
from app.services.buddy_provider import BuddyProviderResponse


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_directory.name) / "workspace.sqlite3"),
            }
        )
        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()
        with self.client.session_transaction() as state:
            state["user_id"] = self.user_id
        workspace_page = self.client.get("/buddy")
        self.csrf_token = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"',
            workspace_page.data,
        ).group(1).decode()

    def post_json(self, path, payload, client=None, csrf_token=None):
        client = client or self.client
        return client.post(
            path,
            json=payload,
            headers={"X-CSRFToken": csrf_token or self.csrf_token},
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_directory.cleanup()

    def test_workspace_requires_authentication(self):
        self.assertEqual(self.app.test_client().get("/workspace").status_code, 302)
        anonymous = self.app.test_client()
        login_page = anonymous.get("/auth/login")
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', login_page.data
        ).group(1).decode()
        response = self.post_json(
            "/api/workspace/diagnostics",
            {"language": "python", "code": "x ="},
            client=anonymous,
            csrf_token=csrf_token,
        )
        self.assertEqual(response.status_code, 401)

    def test_workspace_page_has_editor_mission_and_unavailable_runner(self):
        response = self.client.get("/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="workspace-code"', response.data)
        self.assertIn(b'id="mission-verify"', response.data)
        self.assertIn(b"Secure runner unavailable", response.data)
        self.assertIn(b"codemirror/5.65.16", response.data)

    def test_python_diagnostics_report_actual_syntax_error_location(self):
        response = self.post_json(
            "/api/workspace/diagnostics", {"language": "python", "code": "print(\n"}
        )
        self.assertEqual(response.status_code, 200)
        diagnostic = response.get_json()["diagnostic"]
        self.assertEqual(response.get_json()["language"], "python")
        self.assertEqual(diagnostic["line"], 1)
        self.assertEqual(diagnostic["code"], "print(")
        self.assertTrue(diagnostic["error"])

    def test_mission_awards_xp_only_after_static_verification(self):
        path = "/api/workspace/missions/average/verify"
        broken = "def average(values):\n    total = 0\n    for value in values:\n        total += value\n    return total / len(value)\n"
        fixed = broken.replace("len(value)", "len(values)")
        failed = self.post_json(path, {"language": "python", "code": broken})
        self.assertFalse(failed.get_json()["passed"])
        self.assertEqual(failed.get_json()["xp_awarded"], 0)

        passed = self.post_json(path, {"language": "python", "code": fixed})
        self.assertTrue(passed.get_json()["passed"])
        self.assertEqual(passed.get_json()["xp_awarded"], 25)
        repeated = self.post_json(path, {"language": "python", "code": fixed})
        self.assertEqual(repeated.get_json()["xp_awarded"], 0)

    def test_non_python_diagnostics_are_honestly_unavailable(self):
        response = self.post_json(
            "/api/workspace/diagnostics",
            {"language": "javascript", "code": "const answer = 42;"},
        )
        self.assertFalse(response.get_json()["available"])
        self.assertIsNone(response.get_json()["diagnostic"])
        self.assertIn("not executed", response.get_json()["message"])

    def test_buddy_editor_request_omits_memory_and_saved_context(self):
        response_data = BuddyProviderResponse(
            provider_name="deterministic-local-mock",
            content="MOCK ONLY: Inspect the denominator.",
            is_mock=True,
        )
        with (
            patch("app.buddy_api._approved_memories", return_value=("unrelated",)),
            patch("app.buddy_api.is_memory_enabled", return_value=True),
            patch("app.buddy_api.generate_response", return_value=response_data) as generate,
        ):
            response = self.post_json(
                "/api/buddy/respond",
                {
                    "message": "Help debug this Python syntax error. Code: print(",
                    "language": "python",
                    "workspace_context": True,
                },
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        provider_request = generate.call_args.args[1]
        self.assertEqual(provider_request.approved_memories, ())
        self.assertEqual(provider_request.context, ())
        self.assertEqual(provider_request.programming_language, "python")