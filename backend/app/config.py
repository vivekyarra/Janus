from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = f"sqlite:///{(Path(__file__).resolve().parents[2] / 'janus.db').as_posix()}"
    seed_demo_catalog: bool = True
    frontend_url: str = "http://localhost:5173"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_mode: str = "test"
    llm_api_key: str = ""
    ai_gateway_api_key: str = ""
    vercel_oidc_token: str = ""
    llm_model: str = "openai/gpt-5-mini"
    signing_private_key_pem: str = ""
    signing_public_key_pem: str = ""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
