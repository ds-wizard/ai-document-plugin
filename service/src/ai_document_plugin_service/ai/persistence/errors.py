class TemplateTitleConflictError(Exception):
    def __init__(self, title: str) -> None:
        self.title = title
        super().__init__(f'Template with title "{title}" already exists.')


class SecretDecryptionError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Stored secret could not be decrypted. Check that the 'encryption_key' config value is the one "
            'the secret was encrypted with.'
        )
