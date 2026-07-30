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
