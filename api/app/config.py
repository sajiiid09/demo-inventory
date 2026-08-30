"""Application settings, read from the environment (or a local .env file).

Defaults match local native development: the Postgres installed on this
machine, on localhost:5432. Docker Compose is the alternative — it publishes
its own Postgres on 5433 to avoid clashing with the native one, and its api
service overrides DATABASE_URL to reach the `postgres` container directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://microloan:123@localhost:5432/microloan"
    jwt_secret: str = "dev-only-secret-please-change-me-32-bytes"
    jwt_algorithm: str = "HS256"
    session_hours: int = 8
    # Comma-separated, the way environment variables actually look.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Opening the app over the network (http://192.168.1.x:3000) makes the
    # browser's call to the API cross-origin, and an exact-match list cannot
    # know the machine's address in advance. This regex accepts loopback and
    # the private LAN ranges on any port — enough for a demo on a laptop or a
    # phone on the same wifi, and no help at all to anything off the network.
    # Narrow it (or set it empty) for anything beyond local development.
    cors_origin_regex: str = (
        r"^https?://("
        r"localhost|127\.\d+\.\d+\.\d+|\[::1\]"
        r"|10\.\d+\.\d+\.\d+"
        r"|192\.168\.\d+\.\d+"
        r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+"
        r")(:\d+)?$"
    )

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
