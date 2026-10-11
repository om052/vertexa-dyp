"""Authenticated JSON API for Buddy's local mock and privacy controls."""

import os
import threading
import time
from collections import deque
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request, session
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.extensions import db
from app.models import BuddyConversation, BuddyMemoryItem, BuddyMessage, User
from app.services.buddy_common import (
    BuddyResourceNotFound,
    ConfirmationRequired,
    ConsentRequired,
    ExternalProviderConsentRequired,
    InvalidBuddyInput,
    LearnerApprovalRequired,
    MemoryDisabled,
)
from app.services.buddy_conversations import (
    append_exchange,
    create_saved_conversation_with_exchange,
    delete_saved_conversation,
    get_saved_conversation,
    get_saved_messages,
    list_saved_conversations,
)
from app.services.buddy_memory import (
    MEMORY_CATEGORIES,
    MEMORY_CONTENT_MAX_LENGTH,
    create_memory_item,
    delete_memory_item,
    edit_memory_item,
    get_privacy_settings,
    is_memory_enabled,
    list_memory_items,
    set_memory_enabled,
)
from app.services.buddy_policy import prepare_buddy_request
from app.services.buddy_provider import (
    MAX_CONTEXT_CHARS,
    MAX_CONTEXT_MESSAGES,
    MAX_LEARNER_MESSAGE_CHARS,
    MAX_MEMORY_CHARS,
    MAX_MEMORY_ITEMS,
    BuddyContextMessage,
    DeterministicMockProvider,
    GeminiProvider,
    InvalidProviderInput,
    MalformedProviderResponse,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
    SUPPORTED_LANGUAGES,
    generate_response,
)


buddy_api = Blueprint("buddy_api", __name__, url_prefix="/api/buddy")
HISTORY_CONSENT_KEY = "buddy_history_consent"
HISTORY_POLICY_VERSION_KEY = "buddy_history_policy_version"
HISTORY_POLICY_VERSION = "buddy-history-v1"
EXTERNAL_CONSENT_KEY = "buddy_gemini_external_consent"
EXTERNAL_CONSENT_POLICY_VERSION_KEY = "buddy_gemini_external_consent_version"
EXTERNAL_CONSENT_POLICY_VERSION = "buddy-gemini-google-unpaid-v1"
MEMORY_POLICY_VERSION = "buddy-memory-v1"
MAX_REQUEST_BYTES = 64 * 1024
DEFAULT_RATE_LIMIT = 30
DEFAULT_RATE_WINDOW_SECONDS = 60
GEMINI_RATE_LIMIT = 5
GEMINI_GLOBAL_RATE_LIMIT = 20


class BuddyRequestLimiter:
    """Small per-process sliding-window limiter keyed by authenticated user."""

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def consume(
        self,
        user_id: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> int | None:
        now = time.monotonic()
        with self._lock:
            timestamps = self._requests.setdefault(user_id, deque())
            while timestamps and timestamps[0] <= now - window_seconds:
                timestamps.popleft()
            if len(timestamps) >= limit:
                return max(1, int(window_seconds - (now - timestamps[0])))
            timestamps.append(now)
            if len(self._requests) > 10_000:
                expired_users = [
                    key
                    for key, values in self._requests.items()
                    if not values or values[-1] <= now - window_seconds
                ]
                for key in expired_users:
                    self._requests.pop(key, None)
            return None


def init_buddy_api(app) -> None:
    if app.config["BUDDY_PROVIDER"] == "gemini":
        provider = GeminiProvider(
            os.environ.get("GEMINI_API_KEY"),
            adult_audience_confirmed=app.config.get(
                "BUDDY_GEMINI_ADULTS_ONLY"
            ),
            free_tier_confirmed=app.config.get(
                "BUDDY_GEMINI_FREE_TIER_CONFIRMED"
            ),
        )
    else:
        provider = DeterministicMockProvider()
    app.extensions["buddy_provider"] = provider
    app.extensions["buddy_request_limiter"] = BuddyRequestLimiter()
    if app.config.get("MAX_CONTENT_LENGTH") is None:
        app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    app.config.setdefault("BUDDY_RATE_LIMIT", DEFAULT_RATE_LIMIT)
    app.config.setdefault(
        "BUDDY_RATE_WINDOW_SECONDS",
        DEFAULT_RATE_WINDOW_SECONDS,
    )
    app.config.setdefault("BUDDY_GEMINI_RATE_LIMIT", GEMINI_RATE_LIMIT)
    app.config.setdefault(
        "BUDDY_GEMINI_GLOBAL_RATE_LIMIT",
        GEMINI_GLOBAL_RATE_LIMIT,
    )
    app.register_blueprint(buddy_api)


def _error(code: str, message: str, status: int):
    response = jsonify(error={"code": code, "message": message})
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _json_body(allowed_fields: set[str]) -> dict:
    if not request.is_json:
        raise _RequestProblem(
            "json_required",
            "A JSON request body is required.",
            415,
        )
    try:
        payload = request.get_json()
    except HTTPException as error:
        if error.code == 413:
            raise
        raise _RequestProblem(
            "invalid_json",
            "The JSON request body is malformed.",
            400,
        ) from error
    if not isinstance(payload, dict):
        raise _RequestProblem(
            "invalid_json",
            "The JSON request body must be an object.",
            400,
        )
    if set(payload) - allowed_fields:
        raise _RequestProblem(
            "unexpected_fields",
            "The request contains unsupported fields.",
            400,
        )
    return payload


class _RequestProblem(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _required_string(payload: dict, field: str, *, maximum: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InvalidBuddyInput(
            f"{field.replace('_', ' ').capitalize()} must contain 1 to "
            f"{maximum} characters."
        )
    return value


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _conversation_json(conversation: BuddyConversation) -> dict:
    return {
        "id": conversation.id,
        "created_at": _timestamp(conversation.created_at),
        "last_meaningful_at": _timestamp(conversation.last_meaningful_at),
        "expires_at": _timestamp(conversation.expires_at),
    }


def _message_json(message: BuddyMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "sequence": message.sequence,
        "content": message.content,
        "created_at": _timestamp(message.created_at),
    }


def _memory_json(item: BuddyMemoryItem) -> dict:
    return {
        "id": item.id,
        "category": item.category,
        "content": item.content,
        "learner_approved_at": _timestamp(item.learner_approved_at),
        "created_at": _timestamp(item.created_at),
        "updated_at": _timestamp(item.updated_at),
    }


def _history_is_enabled() -> bool:
    return (
        session.get(HISTORY_CONSENT_KEY) is True
        and session.get(HISTORY_POLICY_VERSION_KEY)
        == HISTORY_POLICY_VERSION
    )


def _external_provider_consent_is_enabled() -> bool:
    return (
        session.get(EXTERNAL_CONSENT_KEY) is True
        and session.get(EXTERNAL_CONSENT_POLICY_VERSION_KEY)
        == EXTERNAL_CONSENT_POLICY_VERSION
        and session.get("buddy_gemini_adult_confirmed") is True
    )


def _configured_mock_provider() -> DeterministicMockProvider | None:
    provider = current_app.extensions.get("buddy_provider")
    if (
        not isinstance(provider, DeterministicMockProvider)
        or provider.is_mock is not True
        or provider.provider_name != DeterministicMockProvider.provider_name
    ):
        return None
    return provider


def _configured_provider():
    provider = current_app.extensions.get("buddy_provider")
    if current_app.config["BUDDY_PROVIDER"] == "mock":
        return _configured_mock_provider()
    if (
        current_app.config["BUDDY_PROVIDER"] == "gemini"
        and isinstance(provider, GeminiProvider)
        and provider.is_mock is False
    ):
        return provider
    return None


@buddy_api.before_request
def require_authenticated_json_user():
    request.max_content_length = MAX_REQUEST_BYTES
    if g.get("current_user") is None:
        return _error(
            "authentication_required",
            "Please sign in to use Buddy.",
            401,
        )

    limit = current_app.config["BUDDY_RATE_LIMIT"]
    window = current_app.config["BUDDY_RATE_WINDOW_SECONDS"]
    retry_after = current_app.extensions["buddy_request_limiter"].consume(
        g.current_user.id,
        limit=limit,
        window_seconds=window,
    )
    if retry_after is not None:
        response = _error(
            "rate_limited",
            "Buddy request limit reached. Please try again shortly.",
            429,
        )
        response.headers["Retry-After"] = str(retry_after)
        return response
    if (
        current_app.config["BUDDY_PROVIDER"] == "gemini"
        and request.endpoint == "buddy_api.respond_to_learner"
    ):
        limiter = current_app.extensions["buddy_request_limiter"]
        retry_after = limiter.consume(
            f"gemini-user:{g.current_user.id}",
            limit=current_app.config["BUDDY_GEMINI_RATE_LIMIT"],
            window_seconds=window,
        )
        if retry_after is None:
            retry_after = limiter.consume(
                "gemini-global",
                limit=current_app.config["BUDDY_GEMINI_GLOBAL_RATE_LIMIT"],
                window_seconds=window,
            )
        if retry_after is not None:
            response = _error(
                "rate_limited",
                "Gemini request limit reached. Wait before trying again.",
                429,
            )
            response.headers["Retry-After"] = str(retry_after)
            return response
    return None


@buddy_api.after_request
def disable_buddy_response_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@buddy_api.errorhandler(CSRFError)
def csrf_error(exception):
    user_id = session.get("user_id")
    authenticated_user = (
        g.get("current_user")
        or (
            db.session.get(User, user_id)
            if isinstance(user_id, str)
            else None
        )
    )
    if authenticated_user is None:
        return _error(
            "authentication_required",
            "Please sign in to use Buddy.",
            401,
        )
    del exception
    return _error(
        "csrf_failed",
        "The request could not be verified. Refresh and try again.",
        400,
    )


@buddy_api.errorhandler(_RequestProblem)
def request_problem(error: _RequestProblem):
    return _error(error.code, error.message, error.status)


@buddy_api.errorhandler(ConsentRequired)
def consent_required(exception):
    del exception
    return _error(
        "history_consent_required",
        "Opt in to saved history before saving a Buddy conversation.",
        409,
    )


@buddy_api.errorhandler(ExternalProviderConsentRequired)
def external_provider_consent_required(exception):
    del exception
    return _error(
        "external_provider_consent_required",
        "Review Google's Gemini data-use notice and explicitly consent before sending a message.",
        409,
    )


@buddy_api.errorhandler(ProviderRateLimited)
def provider_rate_limited(exception):
    del exception
    return _error(
        "provider_rate_limited",
        "Gemini's quota or rate limit was reached. No mock fallback was used.",
        429,
    )


@buddy_api.errorhandler(ConfirmationRequired)
def confirmation_required(exception):
    del exception
    return _error(
        "confirmation_required",
        "Confirm deletion of existing memory before disabling it.",
        409,
    )


@buddy_api.errorhandler(MemoryDisabled)
def memory_disabled(exception):
    del exception
    return _error(
        "memory_disabled",
        "Enable Buddy memory before saving memory items.",
        409,
    )


@buddy_api.errorhandler(LearnerApprovalRequired)
def learner_approval_required(exception):
    del exception
    return _error(
        "learner_approval_required",
        "Explicit approval is required for this memory change.",
        400,
    )


@buddy_api.errorhandler(BuddyResourceNotFound)
def resource_not_found(exception):
    del exception
    return _error("not_found", "The requested Buddy resource was not found.", 404)


@buddy_api.errorhandler(InvalidBuddyInput)
@buddy_api.errorhandler(InvalidProviderInput)
def invalid_input(exception):
    del exception
    return _error("invalid_input", "The Buddy request is invalid.", 400)


@buddy_api.errorhandler(ProviderUnavailable)
def provider_unavailable(exception):
    del exception
    return _error(
        "provider_unavailable",
        "Buddy is temporarily unavailable. Please try again.",
        503,
    )


@buddy_api.errorhandler(ProviderTimeout)
def provider_timeout(exception):
    del exception
    return _error(
        "provider_timeout",
        "Buddy did not respond in time. Please try again.",
        504,
    )


@buddy_api.errorhandler(MalformedProviderResponse)
def malformed_provider_response(exception):
    del exception
    return _error(
        "provider_error",
        "Buddy returned an invalid response. Please try again.",
        502,
    )


@buddy_api.errorhandler(SQLAlchemyError)
def database_error(exception):
    del exception
    db.session.rollback()
    current_app.logger.error("Buddy API storage operation failed.")
    return _error(
        "storage_unavailable",
        "Buddy could not complete the request. Please try again.",
        503,
    )


@buddy_api.errorhandler(HTTPException)
def http_error(error: HTTPException):
    if error.code == 413:
        return _error(
            "request_too_large",
            "The Buddy request exceeds the allowed size.",
            413,
        )
    return _error(
        "request_error",
        "The Buddy request could not be processed.",
        error.code or 400,
    )


@buddy_api.errorhandler(Exception)
def unexpected_error(exception):
    del exception
    current_app.logger.error("Buddy API request failed.")
    return _error(
        "internal_error",
        "Buddy could not complete the request. Please try again.",
        500,
    )


@buddy_api.get("/status")
def buddy_status():
    settings = get_privacy_settings(g.current_user.id)
    provider = current_app.extensions.get("buddy_provider")
    provider_name = getattr(provider, "provider_name", None)
    provider_is_mock = getattr(provider, "is_mock", None)
    provider_available = (
        _configured_provider() is not None
        and getattr(_configured_provider(), "is_available", True) is True
    )
    provider_mode = current_app.config["BUDDY_PROVIDER"]
    availability_message = getattr(provider, "availability_message", "")
    return jsonify(
        available=provider_available,
        provider={
            "name": provider_name if isinstance(provider_name, str) else None,
            "is_mock": provider_is_mock is True,
            "mode": provider_mode,
            "message": availability_message,
        },
        external_consent={
            "required": provider_mode == "gemini",
            "consent": (
                _external_provider_consent_is_enabled()
                if provider_mode == "gemini"
                else False
            ),
            "consent_scope": "authenticated_session",
        },
        history={
            "consent": _history_is_enabled(),
            "consent_scope": "authenticated_session",
        },
        memory={
            "enabled": bool(settings and settings.memory_enabled),
            "consent_at": (
                _timestamp(settings.memory_consent_at)
                if settings and settings.memory_consent_at
                else None
            ),
        },
    )


@buddy_api.post("/external-consent")
def update_external_provider_consent():
    payload = _json_body({"consent", "adult_confirmed"})
    consent = payload.get("consent")
    if not isinstance(consent, bool):
        raise InvalidBuddyInput("External provider consent must be a boolean.")
    if current_app.config["BUDDY_PROVIDER"] != "gemini":
        raise InvalidBuddyInput(
            "External provider consent is only available in Gemini mode."
        )
    if consent:
        provider = _configured_provider()
        if provider is None or not provider.is_available:
            raise ProviderUnavailable(
                getattr(provider, "availability_message", "")
                or "Gemini is not available."
            )
        if payload.get("adult_confirmed") is not True:
            raise InvalidBuddyInput(
                "An adult-only eligibility confirmation is required."
            )
        session[EXTERNAL_CONSENT_KEY] = True
        session[EXTERNAL_CONSENT_POLICY_VERSION_KEY] = (
            EXTERNAL_CONSENT_POLICY_VERSION
        )
        session["buddy_gemini_adult_confirmed"] = True
    else:
        session.pop(EXTERNAL_CONSENT_KEY, None)
        session.pop(EXTERNAL_CONSENT_POLICY_VERSION_KEY, None)
        session.pop("buddy_gemini_adult_confirmed", None)
    return jsonify(
        external_consent={
            "consent": consent,
            "consent_scope": "authenticated_session",
            "policy_version": (
                EXTERNAL_CONSENT_POLICY_VERSION if consent else None
            ),
        }
    )


@buddy_api.post("/history-consent")
def update_history_consent():
    payload = _json_body({"consent"})
    consent = payload.get("consent")
    if not isinstance(consent, bool):
        raise InvalidBuddyInput("History consent must be a boolean.")
    if consent:
        session[HISTORY_CONSENT_KEY] = True
        session[HISTORY_POLICY_VERSION_KEY] = HISTORY_POLICY_VERSION
    else:
        session.pop(HISTORY_CONSENT_KEY, None)
        session.pop(HISTORY_POLICY_VERSION_KEY, None)
    return jsonify(
        history={
            "consent": consent,
            "consent_scope": "authenticated_session",
            "policy_version": HISTORY_POLICY_VERSION if consent else None,
        }
    )


def _build_context(messages: list[BuddyMessage]) -> tuple[BuddyContextMessage, ...]:
    selected: list[BuddyContextMessage] = []
    total_chars = 0
    for message in reversed(messages):
        if len(selected) >= MAX_CONTEXT_MESSAGES:
            break
        if total_chars + len(message.content) > MAX_CONTEXT_CHARS:
            break
        selected.append(
            BuddyContextMessage(role=message.role, content=message.content)
        )
        total_chars += len(message.content)
    selected.reverse()
    return tuple(selected)


def _approved_memories(user_id: str) -> tuple[str, ...]:
    if not is_memory_enabled(user_id):
        return ()
    selected: list[str] = []
    total_chars = 0
    for item in list_memory_items(user_id):
        if len(selected) >= MAX_MEMORY_ITEMS:
            break
        if total_chars + len(item.content) > MAX_MEMORY_CHARS:
            break
        selected.append(item.content)
        total_chars += len(item.content)
    return tuple(selected)


@buddy_api.post("/respond")
def respond_to_learner():
    provider = _configured_provider()
    if provider is None:
        raise ProviderUnavailable("The selected Buddy provider is unavailable.")
    if not getattr(provider, "is_available", True):
        raise ProviderUnavailable(provider.availability_message)

    payload = _json_body(
        {"message", "conversation_id", "language", "workspace_context"}
    )
    learner_message = _required_string(
        payload,
        "message",
        maximum=MAX_LEARNER_MESSAGE_CHARS,
    )
    conversation_id = payload.get("conversation_id")
    if conversation_id is not None and (
        not isinstance(conversation_id, str) or not conversation_id.strip()
    ):
        raise InvalidBuddyInput("Conversation ID is invalid.")
    language = payload.get("language")
    if language is not None and (
        not isinstance(language, str) or language not in SUPPORTED_LANGUAGES
    ):
        raise InvalidBuddyInput("Unsupported programming language.")
    workspace_context = payload.get("workspace_context", False)
    if not isinstance(workspace_context, bool):
        raise InvalidBuddyInput("Workspace context must be a boolean.")
    if workspace_context and conversation_id is not None:
        raise InvalidBuddyInput(
            "Workspace requests cannot include saved conversation context."
        )

    history_enabled = _history_is_enabled()
    gemini_mode = current_app.config["BUDDY_PROVIDER"] == "gemini"
    if gemini_mode and not _external_provider_consent_is_enabled():
        raise ExternalProviderConsentRequired()
    if conversation_id is not None and not history_enabled:
        raise ConsentRequired("Saved history consent is required.")

    context: tuple[BuddyContextMessage, ...] = ()
    if conversation_id is not None:
        saved_messages = get_saved_messages(g.current_user.id, conversation_id)
        if not gemini_mode:
            context = _build_context(saved_messages)

    provider_request, decision = prepare_buddy_request(
        learner_message,
        context=context,
        approved_memories=(
            ()
            if gemini_mode or workspace_context
            else _approved_memories(g.current_user.id)
        ),
        memory_enabled=(
            False
            if gemini_mode or workspace_context
            else is_memory_enabled(g.current_user.id)
        ),
        programming_language=language,
    )
    result = generate_response(
        provider,
        provider_request,
    )
    expected_mock = current_app.config["BUDDY_PROVIDER"] == "mock"
    expected_provider_name = (
        DeterministicMockProvider.provider_name
        if expected_mock
        else GeminiProvider.provider_name
    )
    if (
        result.provider_name != expected_provider_name
        or result.is_mock is not expected_mock
        or (expected_mock and not result.content.startswith("MOCK ONLY:"))
    ):
        raise MalformedProviderResponse(
            "The configured mock provider returned an unexpected response."
        )

    saved_conversation = None
    if history_enabled:
        if conversation_id is None:
            saved_conversation, _ = create_saved_conversation_with_exchange(
                g.current_user.id,
                history_consent=True,
                policy_version=HISTORY_POLICY_VERSION,
                user_content=learner_message,
                assistant_content=result.content,
            )
        else:
            append_exchange(
                g.current_user.id,
                conversation_id,
                user_content=learner_message,
                assistant_content=result.content,
            )
            saved_conversation = get_saved_conversation(
                g.current_user.id,
                conversation_id,
            )

    return jsonify(
        response={
            "content": result.content,
            "provider": result.provider_name,
            "is_mock": result.is_mock,
            "intent": decision.intent,
            "teaching_approach": decision.approach,
        },
        conversation=(
            _conversation_json(saved_conversation)
            if saved_conversation is not None
            else None
        ),
        saved=history_enabled,
    )


@buddy_api.get("/conversations")
def conversations_list():
    return jsonify(
        conversations=[
            _conversation_json(conversation)
            for conversation in list_saved_conversations(g.current_user.id)
        ]
    )


@buddy_api.get("/conversations/<conversation_id>")
def conversation_detail(conversation_id: str):
    conversation = get_saved_conversation(g.current_user.id, conversation_id)
    return jsonify(
        conversation=_conversation_json(conversation),
        messages=[
            _message_json(message)
            for message in get_saved_messages(
                g.current_user.id,
                conversation_id,
            )
        ],
    )


@buddy_api.delete("/conversations/<conversation_id>")
def conversation_delete(conversation_id: str):
    get_saved_conversation(g.current_user.id, conversation_id)
    delete_saved_conversation(g.current_user.id, conversation_id)
    return jsonify(deleted=True)


@buddy_api.get("/privacy")
def privacy_settings():
    settings = get_privacy_settings(g.current_user.id)
    return jsonify(
        privacy={
            "memory_enabled": bool(settings and settings.memory_enabled),
            "memory_consent_at": (
                _timestamp(settings.memory_consent_at)
                if settings and settings.memory_consent_at
                else None
            ),
            "memory_policy_version": (
                settings.memory_policy_version if settings else None
            ),
        }
    )


@buddy_api.patch("/privacy")
def update_privacy_settings():
    payload = _json_body({"memory_enabled", "confirm_delete_existing"})
    enabled = payload.get("memory_enabled")
    if not isinstance(enabled, bool):
        raise InvalidBuddyInput("Memory enabled must be a boolean.")
    confirm = payload.get("confirm_delete_existing", False)
    if not isinstance(confirm, bool):
        raise InvalidBuddyInput("Memory deletion confirmation must be a boolean.")
    result = set_memory_enabled(
        g.current_user.id,
        enabled=enabled,
        policy_version=MEMORY_POLICY_VERSION if enabled else None,
        confirm_delete_existing=confirm,
    )
    settings = get_privacy_settings(g.current_user.id)
    return jsonify(
        privacy={
            "memory_enabled": result,
            "memory_consent_at": (
                _timestamp(settings.memory_consent_at)
                if settings and settings.memory_consent_at
                else None
            ),
            "memory_policy_version": (
                settings.memory_policy_version if settings else None
            ),
        }
    )


@buddy_api.get("/memory")
def memory_list():
    return jsonify(
        memory_enabled=is_memory_enabled(g.current_user.id),
        items=[
            _memory_json(item)
            for item in list_memory_items(g.current_user.id)
        ],
    )


@buddy_api.post("/memory")
def memory_create():
    payload = _json_body({"category", "content", "learner_approved"})
    category = payload.get("category")
    if not isinstance(category, str) or category not in MEMORY_CATEGORIES:
        raise InvalidBuddyInput("Choose a permitted Buddy memory category.")
    content = _required_string(
        payload,
        "content",
        maximum=MEMORY_CONTENT_MAX_LENGTH,
    )
    item = create_memory_item(
        g.current_user.id,
        category=category,
        content=content,
        learner_approved=payload.get("learner_approved") is True,
    )
    return jsonify(item=_memory_json(item)), 201


@buddy_api.patch("/memory/<item_id>")
def memory_update(item_id: str):
    payload = _json_body({"category", "content", "learner_approved"})
    category = payload.get("category")
    if not isinstance(category, str) or category not in MEMORY_CATEGORIES:
        raise InvalidBuddyInput("Choose a permitted Buddy memory category.")
    content = _required_string(
        payload,
        "content",
        maximum=MEMORY_CONTENT_MAX_LENGTH,
    )
    item = edit_memory_item(
        g.current_user.id,
        item_id,
        category=category,
        content=content,
        learner_approved=payload.get("learner_approved") is True,
    )
    return jsonify(item=_memory_json(item))


@buddy_api.delete("/memory/<item_id>")
def memory_delete(item_id: str):
    delete_memory_item(g.current_user.id, item_id)
    return jsonify(deleted=True)
