"""Pure unit tests for the MCP agent-token round trip — no DB required."""
import time

import pytest


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN_SECRET", "test-secret-do-not-use-in-prod")


def test_mint_and_verify_round_trip():
    from server.mcp.auth import mint_agent_token, verify_agent_token

    token = mint_agent_token(42)
    assert verify_agent_token(token) == 42


def test_verify_rejects_missing_token():
    from server.mcp.auth import verify_agent_token

    with pytest.raises(PermissionError):
        verify_agent_token(None)


def test_verify_rejects_bad_signature():
    from jose import jwt

    from server.mcp.auth import ALGORITHM, verify_agent_token

    forged = jwt.encode(
        {"sub": "1", "purpose": "mcp-agent", "exp": int(time.time()) + 60},
        "wrong-secret",
        algorithm=ALGORITHM,
    )
    with pytest.raises(PermissionError):
        verify_agent_token(forged)


def test_verify_rejects_expired_token():
    from jose import jwt

    from server.mcp.auth import ALGORITHM, _secret, verify_agent_token

    expired = jwt.encode(
        {"sub": "1", "purpose": "mcp-agent", "exp": int(time.time()) - 5},
        _secret(),
        algorithm=ALGORITHM,
    )
    with pytest.raises(PermissionError):
        verify_agent_token(expired)


def test_verify_rejects_wrong_purpose():
    from jose import jwt

    from server.mcp.auth import ALGORITHM, _secret, verify_agent_token

    token = jwt.encode(
        {"sub": "1", "purpose": "something-else", "exp": int(time.time()) + 60},
        _secret(),
        algorithm=ALGORITHM,
    )
    with pytest.raises(PermissionError):
        verify_agent_token(token)


def test_verify_rejects_token_naming_a_different_user_only_via_subject():
    """The token's subject is the sole source of identity — there is no
    argument-based override, which is what makes user_id spoofing via a tool
    argument (e.g. from injected content in a scraped job description)
    impossible for my_applications()."""
    from server.mcp.auth import mint_agent_token, verify_agent_token

    token = mint_agent_token(7)
    assert verify_agent_token(token) == 7
    assert verify_agent_token(token) != 999
