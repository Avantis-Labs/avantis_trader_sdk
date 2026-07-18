"""Typed error taxonomy for the Avantis SDK.

Every failure surface (tx-builder envelope errors, relayer failures, RPC
errors, signing mismatches, local validation) maps to one of these classes so
callers can handle them programmatically.
"""

from __future__ import annotations

from typing import Any


class AvantisError(Exception):
    """Base class for all SDK errors."""


class ConfigError(AvantisError):
    """Invalid or incomplete SDK configuration."""


class ApiError(AvantisError):
    """An Avantis HTTP API returned an error envelope or bad status.

    Attributes mirror the tx-builder error envelope:
    ``{ ok: false, error: { code, message, details } }``.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "UNKNOWN",
        status: int | None = None,
        details: Any = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details
        self.url = url

    def __repr__(self) -> str:  # pragma: no cover
        return f"ApiError(code={self.code!r}, status={self.status}, message={self.args[0]!r})"


class ValidationError(ApiError):
    """400 VALIDATION_ERROR / BAD_REQUEST — pre-trade or request-shape failure."""


class RateLimitedError(ApiError):
    """429 RATE_LIMITED."""


class GeoRestrictedError(ApiError):
    """451 GEO_RESTRICTED."""


class SimulationFailedError(ApiError):
    """Relay simulation reverted; ``details`` may carry the decoded error."""


class UpstreamError(ApiError):
    """502 UPSTREAM_ERROR / RPC_ERROR from the API side."""


class SigningError(AvantisError):
    """Local signing failure."""


class DigestMismatchError(SigningError):
    """Locally computed EIP-712 digest differs from the API-provided digest.

    NEVER submit after this error — it means encoding drift between the SDK
    and the API/contracts.
    """


class RelayError(AvantisError):
    """Operator relayer rejected or failed a queued request."""

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id


class RelayTimeoutError(RelayError):
    """Relayer did not settle the request within the polling window."""


class RpcError(AvantisError):
    """JSON-RPC failure when using the direct route."""

    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class TransactionRevertedError(AvantisError):
    """An on-chain transaction was mined but reverted."""

    def __init__(self, message: str, *, tx_hash: str | None = None) -> None:
        super().__init__(message)
        self.tx_hash = tx_hash


class DelegationError(AvantisError):
    """Delegation is missing, disabled, or expired for the configured signer."""


ERROR_CODE_MAP: dict[str, type[ApiError]] = {
    "VALIDATION_ERROR": ValidationError,
    "BAD_REQUEST": ValidationError,
    "TX_REJECTED": ValidationError,
    "SIMULATION_FAILED": SimulationFailedError,
    "RATE_LIMITED": RateLimitedError,
    "GEO_RESTRICTED": GeoRestrictedError,
    "UPSTREAM_ERROR": UpstreamError,
    "RPC_ERROR": UpstreamError,
}


def api_error_from_envelope(
    error: dict[str, Any], *, status: int | None = None, url: str | None = None
) -> ApiError:
    """Build the right ApiError subclass from a tx-builder error envelope."""
    code = str(error.get("code", "UNKNOWN"))
    message = str(error.get("message", "unknown API error"))
    cls = ERROR_CODE_MAP.get(code, ApiError)
    return cls(message, code=code, status=status, details=error.get("details"), url=url)
