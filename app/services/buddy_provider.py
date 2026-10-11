"""Provider-neutral contracts and a deterministic, local-only Buddy mock."""

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


SUPPORTED_LANGUAGES = frozenset({"python", "javascript", "c", "cpp"})
MAX_LEARNER_MESSAGE_CHARS = 12_000
MAX_SYSTEM_INSTRUCTIONS_CHARS = 8_000
MAX_CONTEXT_MESSAGES = 20
MAX_CONTEXT_CHARS = 24_000
MAX_MEMORY_ITEMS = 20
MAX_MEMORY_CHARS = 5_000
MAX_OUTPUT_CHARS = 4_000
MIN_OUTPUT_CHARS = 10

TeachingApproach = Literal[
    "hint_first",
    "simpler_explanation",
    "guided_example",
    "offer_solution",
    "complete_solution",
    "direct_answer",
    "evidence_based_debugging",
]

_TEACHING_APPROACHES = frozenset(
    {
        "hint_first",
        "simpler_explanation",
        "guided_example",
        "offer_solution",
        "complete_solution",
        "direct_answer",
        "evidence_based_debugging",
    }
)


class BuddyAIError(Exception):
    """Base error for Buddy provider and policy operations."""


class InvalidProviderInput(BuddyAIError):
    """Raised when structured provider input violates its contract."""


class ProviderUnavailable(BuddyAIError):
    """Raised when a provider cannot accept a request."""


class ProviderTimeout(BuddyAIError):
    """Raised when a provider request exceeds its allowed time."""


class MalformedProviderResponse(BuddyAIError):
    """Raised when a provider returns a response outside its contract."""


@dataclass(frozen=True)
class BuddyContextMessage:
    """One explicitly supplied, untrusted conversation-context message."""

    role: Literal["user", "assistant"]
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or self.role not in {
            "user",
            "assistant",
        }:
            raise InvalidProviderInput("Context roles must be user or assistant.")
        if (
            not isinstance(self.content, str)
            or not self.content.strip()
            or len(self.content) > MAX_LEARNER_MESSAGE_CHARS
        ):
            raise InvalidProviderInput("Context message content is invalid.")


@dataclass(frozen=True)
class BuddyProviderRequest:
    """Validated request passed to any provider implementation."""

    system_instructions: str
    learner_message: str
    context: tuple[BuddyContextMessage, ...] = ()
    approved_memories: tuple[str, ...] = ()
    programming_language: str | None = None
    max_output_chars: int = 1_000
    teaching_approach: TeachingApproach = "hint_first"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.system_instructions, str)
            or not self.system_instructions.strip()
            or len(self.system_instructions) > MAX_SYSTEM_INSTRUCTIONS_CHARS
        ):
            raise InvalidProviderInput("Trusted teaching instructions are invalid.")
        if (
            not isinstance(self.learner_message, str)
            or not self.learner_message.strip()
            or len(self.learner_message) > MAX_LEARNER_MESSAGE_CHARS
        ):
            raise InvalidProviderInput(
                "Learner message must contain 1 to "
                f"{MAX_LEARNER_MESSAGE_CHARS} characters."
            )
        if not isinstance(self.context, tuple) or any(
            not isinstance(message, BuddyContextMessage)
            for message in self.context
        ):
            raise InvalidProviderInput("Conversation context has an invalid shape.")
        if len(self.context) > MAX_CONTEXT_MESSAGES:
            raise InvalidProviderInput(
                f"Context may contain at most {MAX_CONTEXT_MESSAGES} messages."
            )
        context_chars = sum(len(message.content) for message in self.context)
        if context_chars > MAX_CONTEXT_CHARS:
            raise InvalidProviderInput("Conversation context is too large.")
        if not isinstance(self.approved_memories, tuple) or any(
            not isinstance(memory, str)
            or not memory.strip()
            or len(memory) > 500
            for memory in self.approved_memories
        ):
            raise InvalidProviderInput("Approved memories have an invalid shape.")
        if len(self.approved_memories) > MAX_MEMORY_ITEMS or sum(
            len(memory) for memory in self.approved_memories
        ) > MAX_MEMORY_CHARS:
            raise InvalidProviderInput("Approved memory context is too large.")
        if self.programming_language is not None and (
            not isinstance(self.programming_language, str)
            or self.programming_language not in SUPPORTED_LANGUAGES
        ):
            raise InvalidProviderInput("Unsupported programming language.")
        if (
            isinstance(self.max_output_chars, bool)
            or not isinstance(self.max_output_chars, int)
            or not MIN_OUTPUT_CHARS
            <= self.max_output_chars
            <= MAX_OUTPUT_CHARS
        ):
            raise InvalidProviderInput(
                f"Output limit must be between {MIN_OUTPUT_CHARS} "
                f"and {MAX_OUTPUT_CHARS} characters."
            )
        if (
            not isinstance(self.teaching_approach, str)
            or self.teaching_approach not in _TEACHING_APPROACHES
        ):
            raise InvalidProviderInput("Teaching approach is invalid.")


@dataclass(frozen=True)
class BuddyProviderResponse:
    """Structured provider output; mock responses are explicitly labeled."""

    provider_name: str
    content: str
    is_mock: bool


@runtime_checkable
class BuddyProvider(Protocol):
    """Synchronous contract implemented by provider adapters."""

    def generate(self, request: BuddyProviderRequest) -> BuddyProviderResponse:
        """Generate a response without persisting the request or response."""


def generate_response(
    provider: BuddyProvider,
    request: BuddyProviderRequest,
) -> BuddyProviderResponse:
    """Call a provider and validate its output at the adapter boundary."""
    if not isinstance(request, BuddyProviderRequest):
        raise InvalidProviderInput("A validated Buddy request is required.")
    try:
        response = provider.generate(request)
    except TimeoutError as error:
        raise ProviderTimeout("Buddy provider request timed out.") from error

    if (
        not isinstance(response, BuddyProviderResponse)
        or not isinstance(response.provider_name, str)
        or not response.provider_name.strip()
        or not isinstance(response.content, str)
        or not response.content.strip()
        or not isinstance(response.is_mock, bool)
        or len(response.content) > request.max_output_chars
    ):
        raise MalformedProviderResponse(
            "Buddy provider returned an invalid or oversized response."
        )
    return response


class DeterministicMockProvider:
    """Return canned test-only guidance; never analyzes or executes learner code."""

    provider_name = "deterministic-local-mock"

    _RESPONSES = {
        "hint_first": (
            "MOCK ONLY: Start by identifying the input, the expected output, "
            "and the smallest next step. The mock has not analyzed or "
            "executed your code."
        ),
        "simpler_explanation": (
            "MOCK ONLY: Let's make this smaller: focus on one idea at a time, "
            "then trace one example by hand. The mock did not execute your code."
        ),
        "guided_example": (
            "MOCK ONLY: Try a tiny example with one input and predict each "
            "step before checking the result. The mock did not execute your code."
        ),
        "offer_solution": (
            "MOCK ONLY: We have worked through several hints. Would you like "
            "the complete solution now? The mock did not execute your code."
        ),
        "complete_solution": (
            "MOCK ONLY: A complete-solution request was recognized. This "
            "provider is a deterministic test double and cannot produce a "
            "task-specific solution or execute submitted code."
        ),
        "direct_answer": (
            "MOCK ONLY: This is a direct-answer path for a straightforward "
            "question. The mock does not perform real AI analysis."
        ),
        "evidence_based_debugging": (
            "MOCK ONLY: Observed evidence: this is a debugging request; the "
            "mock has not verified runtime output. Hypothesis: inspect the "
            "first reported error and the values at that point. The mock did "
            "not execute submitted code."
        ),
    }

    def generate(self, request: BuddyProviderRequest) -> BuddyProviderResponse:
        if not isinstance(request, BuddyProviderRequest):
            raise InvalidProviderInput("A validated Buddy request is required.")
        content = self._RESPONSES[request.teaching_approach]
        if request.programming_language:
            content += f" Language context: {request.programming_language}."
        content = content[: request.max_output_chars].rstrip()
        return BuddyProviderResponse(
            provider_name=self.provider_name,
            content=content,
            is_mock=True,
        )
