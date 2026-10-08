from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIRMADOC_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./firmadoc.db"
    storage_dir: str = "./data/storage"
    local_cert_dir: str = "./data/local-cert"
    public_base_url: str = "http://localhost:8000"
    challenge_ttl_seconds: int = 300
    max_document_bytes: int = 20 * 1024 * 1024
    trust_dir: str = "backend/trust"
    revocation_mode: str = "soft-fail"  # hard-fail | soft-fail | off
    revocation_fetch: bool = True  # consultar CRL/OCSP por red
    crl_dir: str | None = None  # CRLs locales (.crl/.der), útil sin salida a internet
    # Widget de firma
    signing_secret: str | None = None  # secreto HMAC de los tokens del widget (>= 32 caracteres)
    signing_token_ttl_seconds: int = 3600
    agent_url: str = "http://127.0.0.1:47123"  # dónde busca el widget al agente local
    widget_dist: str = "widget/dist"  # widget compilado
    max_batch_size: int = 50  # documentos por lote de firma
    admin_token: str | None = None  # token de administración (>= 32 caracteres); sin él, deshabilitada
    # Firma remota (`firmar`): habilitada solo con firmar_base_url
    firmar_base_url: str | None = None
    firmar_client_id: str = "firmadoc"
    firmar_client_secret: str | None = None
    firmar_callback_secret: str | None = None  # HMAC del callback (>= 32 caracteres)
    firmar_timeout_seconds: float = 10.0
    firmar_mock_enabled: bool = False  # servicio simulado (solo desarrollo y pruebas)
    # Sello de tiempo (RFC 3161). Sin tsa_url las firmas son B-B.
    tsa_url: str | None = None
    tsa_timeout_seconds: float = 10.0
    tsa_required: bool = False  # True: sin sello no se firma (503, reintentable)
    # Webhooks al integrador
    webhook_allow_http: bool = False  # solo desarrollo: permite http://
    webhook_allow_private_hosts: bool = False  # solo desarrollo y pruebas: permite hosts privados
    webhook_timeout_seconds: float = 5.0
    webhook_worker_enabled: bool = True
    webhook_poll_seconds: float = 5.0

    @field_validator("tsa_url", "firmar_base_url", mode="before")
    @classmethod
    def _check_tsa_url(cls, value):
        if value is None or value == "":
            return None
        if not str(value).startswith(("http://", "https://")):
            raise ValueError("la URL debe empezar con http:// o https://")
        return value

    @field_validator("signing_secret", "admin_token", "firmar_callback_secret", mode="before")
    @classmethod
    def _check_secret(cls, value):
        if value is None or value == "":
            return None
        if len(str(value)) < MIN_SECRET_LENGTH:
            raise ValueError(f"el secreto debe tener al menos {MIN_SECRET_LENGTH} caracteres")
        return value


def get_settings() -> Settings:
    return Settings()
