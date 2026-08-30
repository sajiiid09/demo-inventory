"""Application settings, read from the environment (or a local .env file).

Defaults match local native development: Postgres on localhost:5433 (the port
docker-compose publishes). Inside docker compose the service environment
overrides DATABASE_URL to reach the `postgres` container directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://microloan:microloan@localhost:5433/microloan"
    jwt_secret: str = "dev-only-secret-please-change-me-32-bytes"
    jwt_algorithm: str = "HS256"
    session_hours: int = 8
    # Comma-separated, the way environment variables actually look.
    cors_origins: str = "http://localhost:3000"

    # --- startup bootstrap (app/bootstrap.py) -------------------------------
    # The demo is meant to run with one command, so the API brings its own
    # database up to date on boot. Each step is idempotent and each can be
    # switched off for an environment that migrates out of band.
    auto_create_database: bool = True   # CREATE DATABASE if it does not exist
    auto_migrate: bool = True           # alembic upgrade head
    auto_seed: bool = True              # demo staff logins + demo portfolio
    # How long to wait for Postgres to accept connections at boot (seconds).
    db_wait_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
