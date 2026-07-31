import pytest

from lmio.routing import CompanyType, route_models


@pytest.mark.parametrize("company_type", list(CompanyType))
def test_every_company_type_has_an_explicit_route(company_type: CompanyType) -> None:
    route = route_models(company_type)

    assert route.preferred_models
    if route.supported_in_v1_engine:
        assert route.warning is None
    else:
        assert "must not be used" in str(route.warning)


def test_bank_and_reit_do_not_route_to_generic_dcf() -> None:
    assert route_models(CompanyType.BANK_INSURANCE).preferred_models == [
        "Residual income",
        "DDM",
        "P/B",
    ]
    assert route_models(CompanyType.REIT).preferred_models == ["AFFO/FFO", "NAV"]


@pytest.mark.parametrize(
    ("case_name", "company_type", "generic_cash_flow_allowed"),
    [
        ("META", CompanyType.HIGH_GROWTH_TECHNOLOGY, True),
        ("stable cash company", CompanyType.STABLE_PROFITABLE, True),
        ("bank", CompanyType.BANK_INSURANCE, False),
        ("REIT", CompanyType.REIT, False),
        ("unprofitable technology", CompanyType.UNPROFITABLE, False),
        ("cyclical", CompanyType.CYCLICAL, False),
    ],
)
def test_required_valuation_acceptance_routes(
    case_name: str,
    company_type: CompanyType,
    generic_cash_flow_allowed: bool,
) -> None:
    route = route_models(company_type)

    assert case_name
    assert route.supported_in_v1_engine is generic_cash_flow_allowed
