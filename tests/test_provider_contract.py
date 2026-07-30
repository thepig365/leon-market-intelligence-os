from lmio.providers import Provider, ProviderHealth, ProviderState


class DisabledSyntheticProvider(Provider):
    name = "synthetic"

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, state=ProviderState.DISABLED)


def test_provider_contract_has_bounded_health() -> None:
    health = DisabledSyntheticProvider().health()

    assert health.provider == "synthetic"
    assert health.state is ProviderState.DISABLED
    assert health.detail == ""
