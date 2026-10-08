"""Servidor HTTP local del agente: dos operaciones, solo en 127.0.0.1, solo para orígenes permitidos."""

import json
import logging
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from . import __version__, errors
from .errors import AgentError
from .service import AgentService

log = logging.getLogger("firmadoc_agent")

BIND_HOST = "127.0.0.1"
MAX_BODY = 1024 * 1024
DRAIN_LIMIT = 64 * 1024
DRAIN_TIMEOUT = 0.2
ROUTES = {"/certificates": "GET", "/sign": "POST"}


class AgentHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # una sola instancia por puerto

    def __init__(self, port: int, service: AgentService, allowed_origins):
        self.service = service
        self.allowed_origins = frozenset(o.lower() for o in allowed_origins)
        super().__init__((BIND_HOST, port), AgentHandler)

    def server_bind(self):
        if os.name == "nt":  # en Windows, REUSEADDR permitiría una segunda instancia
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    @property
    def port(self) -> int:
        return self.server_address[1]


def create_server(service: AgentService, allowed_origins, port: int) -> AgentHTTPServer:
    return AgentHTTPServer(port, service, allowed_origins)


class AgentHandler(BaseHTTPRequestHandler):
    server: AgentHTTPServer
    server_version = "FirmadocAgent"
    sys_version = ""

    def log_message(self, format, *args):
        log.debug("http " + format, *args)

    # -- entrada ---------------------------------------------------------------------------

    def _dispatch(self):
        self._cors_origin: str | None = None
        self._body_read = False
        try:
            self._check_host()
            path = urlsplit(self.path).path
            expected_method = ROUTES.get(path)
            if expected_method is None:
                raise AgentError("not_found", "ruta inexistente", 404)
            if self.command == "OPTIONS":
                return self._preflight(expected_method)
            if self.command != expected_method:
                raise AgentError("method_not_allowed", "método no permitido", 405)
            self._check_origin()
            if path == "/certificates":
                return self._send(200, self.server.service.list_certificates())
            return self._send(200, self.server.service.sign(self._read_json(), self._cors_origin))
        except AgentError as e:
            self._send(e.status, {"code": e.code, "detail": e.detail})
        except Exception:
            log.exception("error inesperado")
            self._send(500, {"code": "internal_error", "detail": "error interno del agente"})

    do_GET = do_POST = do_OPTIONS = do_PUT = do_DELETE = do_PATCH = do_HEAD = _dispatch

    # -- controles de seguridad -------------------------------------------------------------

    def _check_host(self):
        allowed = {f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}"}
        if (self.headers.get("Host") or "").lower() not in allowed:
            raise errors.host_not_allowed()

    def _check_origin(self):
        origin = (self.headers.get("Origin") or "").lower()
        if not origin or origin not in self.server.allowed_origins:
            raise errors.origin_not_allowed()
        self._cors_origin = origin

    def _preflight(self, method: str):
        self._check_origin()
        headers = {
            "Access-Control-Allow-Methods": f"{method}, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        }
        if self.headers.get("Access-Control-Request-Private-Network", "").lower() == "true":
            headers["Access-Control-Allow-Private-Network"] = "true"
        self.send_response(204)
        self._common_headers(headers)
        self.end_headers()

    def _read_json(self):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise AgentError("unsupported_media_type", "se exige Content-Type: application/json", 415)
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise AgentError("length_required", "falta Content-Length", 411) from None
        if length < 0 or length > MAX_BODY:
            raise AgentError("payload_too_large", "el cuerpo supera 1 MiB", 413)
        raw = self.rfile.read(length)
        self._body_read = True
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise errors.invalid_request("el cuerpo no es JSON válido") from None

    # -- salida ----------------------------------------------------------------------------

    def _common_headers(self, extra: dict | None = None):
        self.send_header("X-Firmadoc-Agent", __version__)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Origin")
        if self._cors_origin:
            self.send_header("Access-Control-Allow-Origin", self._cors_origin)
        for name, value in (extra or {}).items():
            self.send_header(name, value)

    def _drain_unread_body(self):
        """Si se rechazó el pedido sin leer su cuerpo, descartar lo que haya llegado.

        Cerrar el socket con datos sin leer provoca un RST (sobre todo en Windows) que puede
        borrar la respuesta antes de que el navegador la lea; el widget no vería el error.
        """
        if self._body_read:
            return
        try:
            length = min(int(self.headers.get("Content-Length") or 0), DRAIN_LIMIT)
            if length > 0:
                self.connection.settimeout(DRAIN_TIMEOUT)
                self.rfile.read1(length) if hasattr(self.rfile, "read1") else self.rfile.read(length)
        except (ValueError, OSError):
            pass
        finally:
            self._body_read = True

    def _send(self, status: int, payload: dict):
        self._drain_unread_body()
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._common_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
