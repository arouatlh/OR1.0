from enum import Enum


class Kind(Enum):
    INTERNAL = "internal"
    BAD_REQUEST = "bad_request"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VALIDATION = "validation"
    UNAVAILABLE = "unavailable"


class AppError(Exception):
    """Opaque: state is private; use the accessors. The original exception is
    attached with `raise AppError(...) from exc` and is for logging only."""

    __slots__ = ("_kind", "_op", "_public", "_issues")

    def __init__(self, kind: Kind, op: str, public: str, issues: tuple[str, ...] = ()):
        super().__init__(op)
        self._kind = kind
        self._op = op
        self._public = public
        self._issues = issues

    @property
    def kind(self) -> Kind:
        return self._kind

    @property
    def op(self) -> str:
        return self._op

    def public_message(self) -> str:
        if self._kind is Kind.INTERNAL:
            return "Something went wrong."
        if self._issues:
            return f"{self._public}: " + "; ".join(self._issues)
        return self._public


def kind_of(exc: BaseException) -> Kind:
    return exc.kind if isinstance(exc, AppError) else Kind.INTERNAL


def public_message(exc: BaseException) -> str:
    return exc.public_message() if isinstance(exc, AppError) else "Something went wrong."


def not_found(op: str, public: str = "Resource not found.") -> AppError:
    return AppError(Kind.NOT_FOUND, op, public)


def conflict(op: str, public: str = "Conflict.") -> AppError:
    return AppError(Kind.CONFLICT, op, public)


def bad_request(op: str, public: str = "Bad request.") -> AppError:
    return AppError(Kind.BAD_REQUEST, op, public)


def validation(op: str, *issues: str) -> AppError:
    return AppError(Kind.VALIDATION, op, "validation failed", issues)


def unavailable(op: str, public: str = "Service temporarily unavailable.") -> AppError:
    return AppError(Kind.UNAVAILABLE, op, public)


def internal(op: str) -> AppError:
    return AppError(Kind.INTERNAL, op, "Something went wrong.")
