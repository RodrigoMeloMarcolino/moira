from contextvars import ContextVar, Token
from dataclasses import dataclass

request_id_var: ContextVar[str | None] = ContextVar('request_id', default=None)
correlation_id_var: ContextVar[str | None] = ContextVar('correlation_id', default=None)


@dataclass(frozen=True)
class LoggingContextTokens:
    request_id: Token[str | None]
    correlation_id: Token[str | None]


def bind_request_context(
    request_id: str,
    correlation_id: str,
) -> LoggingContextTokens:
    return LoggingContextTokens(
        request_id=request_id_var.set(request_id),
        correlation_id=correlation_id_var.set(correlation_id),
    )


def reset_request_context(tokens: LoggingContextTokens) -> None:
    correlation_id_var.reset(tokens.correlation_id)
    request_id_var.reset(tokens.request_id)


def current_request_context() -> dict[str, str]:
    context: dict[str, str] = {}
    request_id = request_id_var.get()
    correlation_id = correlation_id_var.get()
    if request_id is not None:
        context['request.id'] = request_id
    if correlation_id is not None:
        context['correlation.id'] = correlation_id
    return context
