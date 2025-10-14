from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hevy_api_key: str | None = None  # for x-api-key scheme
    hevy_token: str | None = None    # for bearer scheme
    hevy_auth_scheme: str = "bearer"  # "bearer" or "x-api-key"
    hevy_base_url: str = "https://api.hevyapp.com"
    database_url: str = "sqlite:///./hevy.db"

    class Config:
        env_file = ".env"
        env_prefix = ""
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
