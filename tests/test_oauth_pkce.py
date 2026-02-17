import pytest

from core.oauth.pkce import generate_code_challenge, generate_code_verifier, validate_code_challenge


def test_code_verifier_generation():
    """Test code verifier generation"""
    verifier = generate_code_verifier()

    # Length check
    assert 43 <= len(verifier) <= 128

    # Character set check
    import re

    assert re.match(r"^[A-Za-z0-9_-]+$", verifier)

    # Uniqueness
    assert verifier != generate_code_verifier()


def test_code_challenge_s256():
    """Test S256 code challenge generation"""
    # RFC 7636 Appendix B example
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

    challenge = generate_code_challenge(verifier, "S256")
    assert challenge == expected


def test_code_challenge_validation():
    """Test PKCE validation"""
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)

    # Valid
    assert validate_code_challenge(verifier, challenge, "S256")

    # Invalid verifier
    assert not validate_code_challenge("wrong", challenge, "S256")

    # Invalid challenge
    assert not validate_code_challenge(verifier, "wrong", "S256")


def test_plain_method_not_allowed():
    """Test that plain method is not allowed (OAuth 2.1)"""
    with pytest.raises(ValueError, match="S256"):
        generate_code_challenge("verifier", "plain")
