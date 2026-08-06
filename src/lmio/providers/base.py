"""Common provider abstraction required by the LMIO architecture."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class ProviderState(StrEnum):
    """Bounded provider readiness states."""

    DISABLED = "disabled"
    CONFIGURED_NOT_VERIFIED = "configured_not_verified"
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Non-sensitive provider health result."""

    provider: str
    state: ProviderState
    detail: str = ""


class Provider(ABC):
    """Interface implemented by each external data or model adapter."""

    name: str

    @abstractmethod
    def health(self) -> ProviderHealth:
        """Return a read-only, non-sensitive provider health result."""
