class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str, code: str | None = None):
        super().__init__(detail)
        self.detail = detail
        self.code = code


class Unauthorized(DomainError):
    status_code = 401


class Forbidden(DomainError):
    status_code = 403


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Unprocessable(DomainError):
    status_code = 422
