from cryptography.fernet import Fernet, InvalidToken

from ai_document_plugin_service.ai.persistence.errors import SecretDecryptionError


class SecretCipher:
    """Encrypts secrets before they are stored in the database."""

    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode('utf-8')).decode('ascii')

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode('ascii')).decode('utf-8')
        except (InvalidToken, UnicodeEncodeError) as error:
            raise SecretDecryptionError from error
