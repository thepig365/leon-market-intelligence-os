import inspect

from lmio.providers import (
    DeferredOptionsFlowProvider,
    DeferredSocialProvider,
    EstimateRevisionProvider,
    FundamentalsProvider,
    InsiderProvider,
    InstitutionalProvider,
    MarketDataProvider,
    NewsProvider,
    ResearchWorker,
)


def test_all_master_spec_provider_categories_have_abstract_contracts() -> None:
    categories = (
        MarketDataProvider,
        FundamentalsProvider,
        EstimateRevisionProvider,
        NewsProvider,
        InstitutionalProvider,
        InsiderProvider,
        ResearchWorker,
        DeferredOptionsFlowProvider,
        DeferredSocialProvider,
    )

    assert all(inspect.isabstract(category) for category in categories)
