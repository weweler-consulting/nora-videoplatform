from app.core.live_call_token import create_action_token, verify_action_token


def test_token_roundtrip():
    tok = create_action_token("imp-1", "approve")
    assert verify_action_token(tok, "approve") == "imp-1"


def test_token_wrong_action_rejected():
    tok = create_action_token("imp-1", "approve")
    assert verify_action_token(tok, "dismiss") is None


def test_token_garbage_rejected():
    assert verify_action_token("nonsense", "approve") is None
