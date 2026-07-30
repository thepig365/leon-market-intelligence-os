"""Category-specific provider contracts shielding core logic from vendor formats."""

from abc import abstractmethod
from typing import Any

from lmio.domain import NewsEvent, SecuritySnapshot
from lmio.providers.base import Provider


class MarketDataProvider(Provider):
    @abstractmethod
    def snapshots(self) -> list[SecuritySnapshot]:
        """Return normalised point-in-time market snapshots."""


class FundamentalsProvider(Provider):
    @abstractmethod
    def fundamentals(self, symbol: str) -> dict[str, Any]:
        """Return versioned, source-attributed financial facts."""


class EstimateRevisionProvider(Provider):
    @abstractmethod
    def revisions(self, symbol: str) -> list[dict[str, Any]]:
        """Return source-attributed estimate revisions."""


class NewsProvider(Provider):
    @abstractmethod
    def events(self) -> list[NewsEvent]:
        """Return normalised events with source URLs and timestamps."""


class InstitutionalProvider(Provider):
    @abstractmethod
    def holdings(self, symbol: str) -> list[dict[str, Any]]:
        """Return source-attributed institutional holdings."""


class InsiderProvider(Provider):
    @abstractmethod
    def transactions(self, symbol: str) -> list[dict[str, Any]]:
        """Return source-attributed insider transactions."""


class ResearchWorker(Provider):
    @abstractmethod
    def analyse(self, evidence: dict[str, Any]) -> dict[str, Any]:
        """Interpret supplied evidence without controlling calculations or orchestration."""


class DeferredOptionsFlowProvider(Provider):
    """V1 interface only; activation requires a later provider decision."""

    @abstractmethod
    def flow(self, symbol: str) -> list[dict[str, Any]]:
        """Return source-attributed options observations."""


class DeferredSocialProvider(Provider):
    """V1 interface only; activation requires a later provider decision."""

    @abstractmethod
    def mentions(self, symbol: str) -> list[dict[str, Any]]:
        """Return source-attributed social observations."""
