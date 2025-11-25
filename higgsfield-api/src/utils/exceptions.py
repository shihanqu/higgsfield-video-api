"""
Custom exceptions for the Higgsfield API service.
"""


class HiggsfieldError(Exception):
    """Base exception for all Higgsfield-related errors."""

    pass


class AuthenticationError(HiggsfieldError):
    """Raised when authentication fails."""

    pass


class AuthStorageError(HiggsfieldError):
    """Raised when there are issues with auth storage (auth.json)."""

    pass


class SessionError(HiggsfieldError):
    """Raised when session management fails."""

    pass


class TokenMintError(HiggsfieldError):
    """Raised when token minting fails."""

    pass


class APIRequestError(HiggsfieldError):
    """Raised when API requests fail."""

    def __init__(
        self, message: str, status_code: int = None, response_data: dict = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class FileUploadError(HiggsfieldError):
    """Raised when file upload operations fail."""

    pass


class VideoGenerationError(HiggsfieldError):
    """Raised when video generation fails."""

    pass


class MotionConfigError(HiggsfieldError):
    """Raised when motion configuration is invalid."""

    pass


class CookieParsingError(HiggsfieldError):
    """Raised when cookie parsing fails."""

    pass
