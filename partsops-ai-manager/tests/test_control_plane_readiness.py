from scripts.validation.validate_control_plane_readiness import run_checks


def test_control_plane_readiness_smoke():
    report = run_checks()

    assert report["ok"] is True
    assert report["checks"]["event_chain_integrity"]["ok"] is True
    assert report["checks"]["event_chain_tamper_detection"]["ok"] is True
    assert report["checks"]["terminal_state_invariant"]["ok"] is True
    assert report["checks"]["pii_masking"]["ok"] is True
