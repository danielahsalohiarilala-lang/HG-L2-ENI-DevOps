from app.core.security import hash_password, verify_password


def test_hash_and_verify():
    h = hash_password("Secret!2026")
    assert h != "Secret!2026"
    assert verify_password("Secret!2026", h)
    assert not verify_password("autre", h)
    assert not verify_password("x", "pas-un-hash")
