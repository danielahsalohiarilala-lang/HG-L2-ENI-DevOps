"""Configuration de l'application, lue depuis les variables d'environnement (.env)."""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "Tantara SaaS"

    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str = "tantara"
    mysql_user: str = "tantara"
    mysql_password: str = "change_me"

    # Permet de forcer une URL complète (utile pour les tests avec SQLite)
    database_url: str | None = None

    # Sécurité (jetons JWT). En dehors du développement, JWT_SECRET doit être défini dans .env
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bcrypt_rounds: int = 12
    login_max_attempts: int = 5
    login_window_seconds: int = 60
    cors_origins: str = "http://localhost:3000"

    admin_email: str = "admin@tantara.mg"
    admin_password: str = "ChangeMe!2026"

    @model_validator(mode="after")
    def _check_secret(self):
        if not self.is_dev and (self.jwt_secret == "dev-only-secret-change-me" or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET doit être défini hors développement (au moins 32 caractères)")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        pwd = quote_plus(self.mysql_password)
        return (f"mysql+asyncmy://{self.mysql_user}:{pwd}@{self.mysql_host}:"
                f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4")

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
