"""Conversational coordinator for Smart Property AI.

This module connects:

- Language selection
- Input safety
- Prompt construction
- Model inference
- Output safety

FastAPI routes should call ask_assistant_async() and return
AssistantResponse.to_dict() as JSON.

This module never logs private message contents, credentials,
or authorized property context.
"""

from __future__ import annotations

import asyncio
import threading

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .inference import (
    InferenceEngine,
    InferenceError,
    create_inference_engine,
    engine_health,
    generate_response_async,
)

from .language import (
    localized_message,
    resolve_response_language,
)

from .prompts import (
    MAX_HISTORY_MESSAGES,
    PromptContext,
    build_chat_messages,
    normalize_role,
)

from .safety import (
    SafetyAction,
    SafetyCategory,
    check_input,
    check_output,
    contains_prompt_injection,
    redact_sensitive_data,
    safe_fallback_message,
)


@dataclass(frozen=True, slots=True)
class AssistantRequest:
    """One request sent to Smart Property AI.

    property_context and authorized_context must contain only
    records that the route or service layer has already
    authorized for the current user.
    """

    message: str

    history: Sequence[
        Mapping[str, object]
    ] = field(
        default_factory=tuple
    )

    requested_language: str | None = None
    session_language: str | None = None
    user_language: str | None = None
    accept_language: str | None = None

    user_role: str = "guest"
    user_name: str | None = None

    page: str | None = None
    intent: str | None = None

    property_context: Mapping[
        str,
        object,
    ] = field(
        default_factory=dict
    )

    authorized_context: Mapping[
        str,
        object,
    ] = field(
        default_factory=dict
    )

    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 600


@dataclass(frozen=True, slots=True)
class AssistantResponse:
    """JSON-ready assistant response."""

    success: bool
    reply: str
    language: str

    blocked: bool = False

    action: str = (
        SafetyAction.ALLOW.value
    )

    categories: tuple[str, ...] = (
        SafetyCategory.SAFE.value,
    )

    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None

    used_fallback: bool = False
    requires_human_review: bool = False
    is_emergency: bool = False

    error_code: str | None = None

    def to_dict(
        self,
    ) -> dict[str, object]:
        """Return a serializable FastAPI response."""

        return {
            "success": self.success,

            # Both names are supplied for compatibility
            # with existing frontend JavaScript.
            "reply": self.reply,
            "message": self.reply,

            "language": self.language,
            "blocked": self.blocked,
            "action": self.action,

            "categories": list(
                self.categories
            ),

            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,

            "used_fallback": self.used_fallback,

            "requires_human_review": (
                self.requires_human_review
            ),

            "is_emergency": self.is_emergency,
            "error_code": self.error_code,
        }


def _category_values(
    categories: Sequence[SafetyCategory],
) -> tuple[str, ...]:
    """Convert categories into JSON values."""

    return tuple(
        category.value
        for category in categories
    )


def _bounded_temperature(
    value: float,
) -> float:
    """Limit model creativity."""

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        number = 0.2

    if number != number:
        number = 0.2

    if number in {
        float("inf"),
        float("-inf"),
    }:
        number = 0.2

    return max(
        0.0,
        min(
            number,
            1.0,
        ),
    )


def _bounded_max_tokens(
    value: int,
) -> int:
    """Limit response token length."""

    try:
        number = int(value)

    except (
        TypeError,
        ValueError,
    ):
        number = 600

    return max(
        50,
        min(
            number,
            2_000,
        ),
    )


def _sanitize_history(
    history: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    """Sanitize browser-supplied conversation history.

    Browser-supplied system and tool messages are rejected.

    Messages containing likely prompt injections are removed.

    Sensitive values are redacted before they reach the
    inference provider.
    """

    sanitized: list[
        dict[str, str]
    ] = []

    for item in history[
        -MAX_HISTORY_MESSAGES:
    ]:
        role = str(
            item.get(
                "role",
                "",
            )
        ).strip().lower()

        if role not in {
            "user",
            "assistant",
        }:
            continue

        content = str(
            item.get(
                "content",
                "",
            )
        )

        content = (
            content
            .replace(
                "\x00",
                "",
            )
            .strip()
        )

        if not content:
            continue

        if contains_prompt_injection(
            content
        ):
            continue

        content = redact_sensitive_data(
            content
        )

        if len(content) > 4_000:
            content = (
                content[:3_999]
                .rstrip()
                + "…"
            )

        sanitized.append(
            {
                "role": role,
                "content": content,
            }
        )

    return sanitized


class SmartPropertyAssistant:
    """Coordinate one complete assistant turn."""

    def __init__(
        self,
        engine: InferenceEngine | None = None,
    ) -> None:
        self.engine = (
            engine
            or create_inference_engine()
        )

    async def respond_async(
        self,
        request: AssistantRequest,
    ) -> AssistantResponse:
        """Process one request asynchronously."""

        language = resolve_response_language(
            request.message,
            requested=(
                request.requested_language
            ),
            session_language=(
                request.session_language
            ),
            user_language=(
                request.user_language
            ),
            accept_language=(
                request.accept_language
            ),
        )

        input_safety = check_input(
            request.message,
            language=language,
        )

        if not input_safety.allowed:
            return AssistantResponse(
                success=True,

                reply=safe_fallback_message(
                    input_safety,
                    language=language,
                ),

                language=language,
                blocked=True,

                action=(
                    input_safety
                    .action
                    .value
                ),

                categories=_category_values(
                    input_safety.categories
                ),

                requires_human_review=(
                    input_safety
                    .requires_human_review
                ),

                is_emergency=(
                    input_safety
                    .is_emergency
                ),
            )

        context = PromptContext(
            language=language,

            user_role=normalize_role(
                request.user_role
            ),

            user_name=request.user_name,
            page=request.page,
            intent=request.intent,

            property_context=(
                request.property_context
            ),

            authorized_context=(
                request.authorized_context
            ),
        )

        try:
            messages = build_chat_messages(
                input_safety.sanitized_text,

                context=context,

                history=_sanitize_history(
                    request.history
                ),
            )

            inference = (
                await generate_response_async(
                    messages,

                    language=language,
                    model=request.model,

                    temperature=(
                        _bounded_temperature(
                            request.temperature
                        )
                    ),

                    max_tokens=(
                        _bounded_max_tokens(
                            request.max_tokens
                        )
                    ),

                    engine=self.engine,

                    metadata={
                        "role": normalize_role(
                            request.user_role
                        ),

                        "page": str(
                            request.page or ""
                        )[:200],

                        "intent": str(
                            request.intent or ""
                        )[:100],
                    },
                )
            )

        except (
            InferenceError,
            OSError,
            ValueError,
            TypeError,
        ):
            return AssistantResponse(
                success=False,

                reply=localized_message(
                    "error",
                    language,
                ),

                language=language,
                blocked=False,

                action=(
                    SafetyAction
                    .BLOCK
                    .value
                ),

                categories=(
                    SafetyCategory
                    .SAFE
                    .value,
                ),

                error_code=(
                    "inference_unavailable"
                ),
            )

        output_safety = check_output(
            inference.text,
            language=language,
        )

        if not output_safety.allowed:
            return AssistantResponse(
                success=True,

                reply=safe_fallback_message(
                    output_safety,
                    language=language,
                ),

                language=language,
                blocked=True,

                action=(
                    output_safety
                    .action
                    .value
                ),

                categories=_category_values(
                    output_safety.categories
                ),

                provider=inference.provider,
                model=inference.model,

                latency_ms=(
                    inference.latency_ms
                ),

                finish_reason=(
                    inference.finish_reason
                ),

                used_fallback=(
                    inference.used_fallback
                ),

                requires_human_review=(
                    output_safety
                    .requires_human_review
                ),

                is_emergency=(
                    output_safety
                    .is_emergency
                ),
            )

        combined_categories = tuple(
            dict.fromkeys(
                _category_values(
                    input_safety.categories
                )
                + _category_values(
                    output_safety.categories
                )
            )
        )

        action = output_safety.action

        if (
            input_safety.action
            == SafetyAction.REDACT
        ):
            action = SafetyAction.REDACT

        return AssistantResponse(
            success=True,

            reply=(
                output_safety
                .sanitized_text
            ),

            language=language,
            blocked=False,

            action=action.value,

            categories=(
                combined_categories
            ),

            provider=inference.provider,
            model=inference.model,

            latency_ms=(
                inference.latency_ms
            ),

            finish_reason=(
                inference.finish_reason
            ),

            used_fallback=(
                inference.used_fallback
            ),

            requires_human_review=(
                output_safety
                .requires_human_review
            ),

            is_emergency=(
                output_safety
                .is_emergency
            ),
        )

    def respond(
        self,
        request: AssistantRequest,
    ) -> AssistantResponse:
        """Process a request from synchronous code.

        FastAPI async routes must use respond_async().
        """

        try:
            asyncio.get_running_loop()

        except RuntimeError:
            return asyncio.run(
                self.respond_async(
                    request
                )
            )

        raise RuntimeError(
            "SmartPropertyAssistant.respond() "
            "cannot run inside an active event loop. "
            "Use await respond_async() instead."
        )

    def health(
        self,
    ) -> dict[str, object]:
        """Return non-sensitive health information."""

        health = engine_health(
            self.engine
        )

        return {
            "available": health.get(
                "available",
                False,
            ),

            "provider": health.get(
                "provider",
                "unknown",
            ),

            "fallback_enabled": health.get(
                "fallback_enabled",
                False,
            ),

            "languages": [
                "en",
                "de",
                "fr",
                "es",
            ],

            "safety_enabled": True,
        }


_assistant_instance: (
    SmartPropertyAssistant | None
) = None

_assistant_lock = threading.Lock()


def get_assistant() -> SmartPropertyAssistant:
    """Return the application-wide assistant."""

    global _assistant_instance

    if _assistant_instance is None:
        with _assistant_lock:
            if _assistant_instance is None:
                _assistant_instance = (
                    SmartPropertyAssistant()
                )

    return _assistant_instance


def configure_assistant(
    engine: InferenceEngine,
) -> SmartPropertyAssistant:
    """Replace the shared engine.

    This can be used during application startup or tests.
    """

    global _assistant_instance

    with _assistant_lock:
        _assistant_instance = (
            SmartPropertyAssistant(
                engine=engine
            )
        )

        return _assistant_instance


async def ask_assistant_async(
    message: str,
    *,
    history: Sequence[
        Mapping[str, object]
    ] | None = None,
    language: str | None = None,
    session_language: str | None = None,
    user_language: str | None = None,
    accept_language: str | None = None,
    user_role: str = "guest",
    user_name: str | None = None,
    page: str | None = None,
    intent: str | None = None,
    property_context: (
        Mapping[str, object] | None
    ) = None,
    authorized_context: (
        Mapping[str, object] | None
    ) = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> AssistantResponse:
    """Asynchronous entry point for FastAPI routes."""

    request = AssistantRequest(
        message=message,
        history=history or (),

        requested_language=language,
        session_language=session_language,
        user_language=user_language,
        accept_language=accept_language,

        user_role=user_role,
        user_name=user_name,

        page=page,
        intent=intent,

        property_context=(
            property_context or {}
        ),

        authorized_context=(
            authorized_context or {}
        ),

        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    assistant = get_assistant()

    return await assistant.respond_async(
        request
    )


def ask_assistant(
    message: str,
    *,
    history: Sequence[
        Mapping[str, object]
    ] | None = None,
    language: str | None = None,
    session_language: str | None = None,
    user_language: str | None = None,
    accept_language: str | None = None,
    user_role: str = "guest",
    user_name: str | None = None,
    page: str | None = None,
    intent: str | None = None,
    property_context: (
        Mapping[str, object] | None
    ) = None,
    authorized_context: (
        Mapping[str, object] | None
    ) = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> AssistantResponse:
    """Synchronous entry point for scripts and tests."""

    request = AssistantRequest(
        message=message,
        history=history or (),

        requested_language=language,
        session_language=session_language,
        user_language=user_language,
        accept_language=accept_language,

        user_role=user_role,
        user_name=user_name,

        page=page,
        intent=intent,

        property_context=(
            property_context or {}
        ),

        authorized_context=(
            authorized_context or {}
        ),

        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    assistant = get_assistant()

    return assistant.respond(
        request
    )


async def generate_reply_async(
    message: str,
    **kwargs: object,
) -> str:
    """Compatibility helper returning only reply text."""

    response = await ask_assistant_async(
        message,
        **kwargs,
    )

    return response.reply


def generate_reply(
    message: str,
    **kwargs: object,
) -> str:
    """Compatibility helper returning only reply text."""

    response = ask_assistant(
        message,
        **kwargs,
    )

    return response.reply


__all__ = [
    "AssistantRequest",
    "AssistantResponse",
    "SmartPropertyAssistant",
    "ask_assistant",
    "ask_assistant_async",
    "configure_assistant",
    "generate_reply",
    "generate_reply_async",
    "get_assistant",
]