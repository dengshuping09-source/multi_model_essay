from app.core.security import hash_password, token_digest, verify_password


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("secure-test-password")
    second = hash_password("secure-test-password")

    assert first != second
    assert verify_password("secure-test-password", first)
    assert not verify_password("wrong-password", first)


def test_session_token_digest_is_deterministic_but_not_the_token() -> None:
    token = "not-a-real-session-token"

    assert token_digest(token) == token_digest(token)
    assert token_digest(token) != token
