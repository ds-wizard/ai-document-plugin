class TemplateTitleConflictError(Exception):
    def __init__(self, title: str) -> None:
        self.title = title
        super().__init__(f'Template with title "{title}" already exists.')
