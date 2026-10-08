"""Errores de dominio del agente. El `code` es estable: lo interpreta el widget."""


class AgentError(Exception):
    def __init__(self, code: str, detail: str, status: int):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def origin_not_allowed(detail: str = "el origen no está permitido") -> AgentError:
    return AgentError("origin_not_allowed", detail, 403)


def host_not_allowed() -> AgentError:
    return AgentError("host_not_allowed", "la cabecera Host no es la del agente local", 403)


def invalid_request(detail: str) -> AgentError:
    return AgentError("invalid_request", detail, 400)


def too_many_items(maximum: int) -> AgentError:
    return AgentError("too_many_items", f"el pedido admite como máximo {maximum} elementos", 413)


def token_not_found() -> AgentError:
    return AgentError("token_not_found", "no hay ningún token conectado", 404)


def certificate_not_found() -> AgentError:
    return AgentError("certificate_not_found", "el certificado no está en el token", 404)


def pkcs11_unavailable(detail: str) -> AgentError:
    return AgentError("pkcs11_unavailable", detail, 500)


def user_cancelled() -> AgentError:
    return AgentError("user_cancelled", "el usuario canceló la firma o no respondió", 409)


def pin_incorrect(detail: str = "PIN incorrecto") -> AgentError:
    return AgentError("pin_incorrect", detail, 401)


def pin_locked() -> AgentError:
    return AgentError("pin_locked", "el PIN del token está bloqueado", 423)


def busy() -> AgentError:
    return AgentError("busy", "ya hay una firma en curso", 429)
