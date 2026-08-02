from lmio.roles import PERMISSIONS, Principal, Role, can


def test_role_matrix_keeps_mutation_out_of_reviewer_role() -> None:
    reviewer = Principal(
        actor_id="reviewer-1",
        role=Role.REVIEWER,
        authentication_method="test",
    )
    assert can(reviewer, "view_evidence")
    assert can(reviewer, "manage_watchlists") is False
    assert "request_refresh" in PERMISSIONS[Role.OWNER]
