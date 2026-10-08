from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIRMADOC_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./firmadoc.db"
    storage_dir: str = "./data/storage"
    local_cert_dir: str = "./data/local-cert"
    public_base_url: str = "http://localhost:8000"
    challenge_ttl_seconds: int = 300
    max_document_bytes: int = 20 * 1024 * 1024


def get_settings() -> Settings:
    return Settings()
