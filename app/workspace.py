"""Authenticated coding workspace routes; learner code is never executed."""

import ast

from flask import Blueprint, g, jsonify, render_template, request, session

from app.auth import login_required


workspace_api = Blueprint("workspace_api", __name__)
SUPPORTED_LANGUAGES = {"python", "javascript", "c", "cpp"}
MAX_CODE_CHARS = 10_000
MISSION_KEY = "workspace_mission_average_verified"


@workspace_api.get("/workspace")
@login_required
def workspace():
    return render_template("workspace.html", page="workspace")


@workspace_api.before_request
def require_workspace_user():
    if request.path.startswith("/api/workspace/") and g.get("current_user") is None:
        return jsonify(error={"message": "Please sign in to use the coding workspace."}), 401
    return None


@workspace_api.after_request
def disable_workspace_api_caching(response):
    if request.path.startswith("/api/workspace/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _workspace_payload(allowed_fields):
    if not request.is_json:
        return None, (jsonify(error={"message": "A JSON request body is required."}), 415)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != allowed_fields:
        return None, (jsonify(error={"message": "The workspace request is invalid."}), 400)
    language = payload.get("language")
    code = payload.get("code")
    if language not in SUPPORTED_LANGUAGES:
        return None, (jsonify(error={"message": "Choose a supported programming language."}), 400)
    if not isinstance(code, str) or len(code) > MAX_CODE_CHARS:
        return None, (jsonify(error={"message": "Code must be at most 10,000 characters."}), 400)
    return payload, None


@workspace_api.post("/api/workspace/diagnostics")
def diagnostics():
    payload, error = _workspace_payload({"language", "code"})
    if error:
        return error

    language = payload["language"]
    if language != "python":
        return jsonify(
            language=language,
            available=False,
            message="Static syntax diagnostics are unavailable for this language. Code was not executed.",
            diagnostic=None,
        )

    try:
        ast.parse(payload["code"])
    except SyntaxError as syntax_error:
        lines = payload["code"].splitlines()
        line = syntax_error.lineno
        return jsonify(
            language=language,
            available=True,
            message="Python syntax error",
            diagnostic={
                "error": syntax_error.msg,
                "line": line,
                "column": syntax_error.offset,
                "code": lines[line - 1] if line and line <= len(lines) else "",
            },
        )

    return jsonify(
        language=language,
        available=True,
        message="No Python syntax errors found. This is not an execution result.",
        diagnostic=None,
    )


def _mission_average_is_fixed(tree):
    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "average"),
        None,
    )
    if (
        function is None
        or len(function.body) != 3
        or len(function.args.args) != 1
        or function.args.args[0].arg != "values"
        or function.args.posonlyargs
        or function.args.kwonlyargs
        or function.args.vararg
        or function.args.kwarg
        or function.decorator_list
    ):
        return False

    initialization, loop, result = function.body
    initialized_total = (
        isinstance(initialization, ast.Assign)
        and len(initialization.targets) == 1
        and isinstance(initialization.targets[0], ast.Name)
        and initialization.targets[0].id == "total"
        and isinstance(initialization.value, ast.Constant)
        and initialization.value.value == 0
    )
    sums_values = (
        isinstance(loop, ast.For)
        and isinstance(loop.target, ast.Name)
        and loop.target.id == "value"
        and isinstance(loop.iter, ast.Name)
        and loop.iter.id == "values"
        and len(loop.body) == 1
        and isinstance(loop.body[0], ast.AugAssign)
        and isinstance(loop.body[0].target, ast.Name)
        and loop.body[0].target.id == "total"
        and isinstance(loop.body[0].op, ast.Add)
        and isinstance(loop.body[0].value, ast.Name)
        and loop.body[0].value.id == "value"
    )
    averages_all_values = (
        isinstance(result, ast.Return)
        and isinstance(result.value, ast.BinOp)
        and isinstance(result.value.op, ast.Div)
        and isinstance(result.value.left, ast.Name)
        and result.value.left.id == "total"
        and isinstance(result.value.right, ast.Call)
        and isinstance(result.value.right.func, ast.Name)
        and result.value.right.func.id == "len"
        and len(result.value.right.args) == 1
        and isinstance(result.value.right.args[0], ast.Name)
        and result.value.right.args[0].id == "values"
    )
    return initialized_total and sums_values and averages_all_values


@workspace_api.post("/api/workspace/missions/average/verify")
def verify_average_mission():
    payload, error = _workspace_payload({"language", "code"})
    if error:
        return error
    if payload["language"] != "python":
        return jsonify(passed=False, message="This mission currently checks Python code."), 400

    try:
        tree = ast.parse(payload["code"])
    except SyntaxError as syntax_error:
        return jsonify(
            passed=False,
            message="Fix the Python syntax error before checking the mission.",
            diagnostic={"error": syntax_error.msg, "line": syntax_error.lineno, "column": syntax_error.offset},
            xp_awarded=0,
        )

    passed = _mission_average_is_fixed(tree)
    xp_awarded = 0
    if passed and not session.get(MISSION_KEY):
        session[MISSION_KEY] = True
        xp_awarded = 25

    return jsonify(
        passed=passed,
        message=(
            "Mission check passed: the function divides by the number of values. This was verified from Python syntax, not by running the program."
            if passed
            else "Not quite. Check which name the denominator counts, then verify again."
        ),
        xp_awarded=xp_awarded,
        total_xp=25 if session.get(MISSION_KEY) else 0,
    )