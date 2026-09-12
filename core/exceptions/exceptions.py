class BaseAppException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(BaseAppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class NotFoundError(BaseAppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class ConfigurationError(BaseAppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class LLMError(BaseAppException):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, status_code=status_code)


class LLMRequestError(LLMError):
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message, status_code=502)
        self.original_error = original_error


class UnsupportedOperationError(BaseAppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)