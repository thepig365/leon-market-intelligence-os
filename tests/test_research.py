from lmio.demo import demo_universe
from lmio.research import build_research_pack
from lmio.screens import run_core_screens
from lmio.universe import build_investable_universe


def test_research_pack_lowers_confidence_without_news_or_valuation() -> None:
    candidate = run_core_screens(build_investable_universe(demo_universe()))[0]

    pack = build_research_pack(candidate, [], None)

    assert pack.symbol == candidate.symbol
    assert pack.confidence < candidate.scores.confidence
    assert "No reproducible valuation is attached." in pack.risks
    assert pack.model_version == "deterministic-research-pack-v2"
    assert pack.company_profile
    assert pack.valuation_summary == "No reproducible valuation is attached."
    assert len(pack.fields) == 15
    assert pack.fields["business_model"][0].classification == "missing"
    assert pack.fields["financial_quality"][0].evidence_references
    assert pack.prompt_template_version == "research-15-fields-v1"
