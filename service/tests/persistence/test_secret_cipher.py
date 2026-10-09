import pytest
from cryptography.fernet import Fernet

from ai_document_plugin_service.ai.persistence.errors import SecretDecryptionError
from ai_document_plugin_service.ai.persistence.secret_cipher import SecretCipher


def _cipher() -> SecretCipher:
    return SecretCipher(Fernet.generate_key().decode())


def test_encrypt_round_trips_and_hides_plaintext() -> None:
    cipher = _cipher()

    encrypted = cipher.encrypt('sk-secret-ključ')

    assert 'sk-secret' not in encrypted
    assert cipher.decrypt(encrypted) == 'sk-secret-ključ'


def test_decrypt_rejects_secret_encrypted_with_another_key() -> None:
    encrypted = _cipher().encrypt('sk-secret')

    with pytest.raises(SecretDecryptionError):
        _cipher().decrypt(encrypted)


@pytest.mark.parametrize('stored', ['sk-plaintext-key', 'ključ'])
def test_decrypt_rejects_plaintext(stored: str) -> None:
    with pytest.raises(SecretDecryptionError):
        _cipher().decrypt(stored)
