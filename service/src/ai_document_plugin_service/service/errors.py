class ServiceError(Exception):
    """HTTP-mappable error raised by service layer code."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class NotFoundError(ServiceError):
    PIPELINE_RUN_MESSAGE = 'Pipeline run not found'
    TEMPLATE_MESSAGE = 'Template not found'

    def __init__(self, detail: str = 'Not found') -> None:
        super().__init__(detail, status_code=404)


class AccessDeniedError(ServiceError):
    def __init__(self, detail: str = 'Access denied') -> None:
        super().__init__(detail, status_code=403)


class ValidationError(ServiceError):
    EMPTY_MARKDOWN_MESSAGE = 'There is no content to export'

    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=400)


class ConflictError(ServiceError):
    PIPELINE_RUN_NOT_FINISHED_MESSAGE = 'Pipeline run has not finished successfully'

    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=409)
