"""Application settings, read from the environment (or a local .env file).

Defaults match local native development: Postgres on localhost:5432.
Inside docker compose the service environment overrides DATABASE_URL.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://microloan:microloan@localhost:5433/microloan"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    session_hours: int = 8
    # Comma-separated, the way environment variables actually look.
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
