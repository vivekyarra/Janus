from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = f"sqlite:///{(Path(__file__).resolve().parents[2] / 'janus.db').as_posix()}"
    seed_demo_catalog: bool = False
    frontend_url: str = "http://localhost:5173"
    razorpay_key_id: str = "rzp_test_TYLX8xpOHRN4ur"
    razorpay_key_secret: str = "82N6NFeF3IffDNTypchZYcP7"
    razorpay_mode: str = "test"
    llm_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    ai_gateway_api_key: str = ""
    vercel_oidc_token: str = ""
    llm_model: str = "openai/gpt-5-mini"
    signing_private_key_pem: str = ""
    signing_public_key_pem: str = ""
    auth_required: bool = False
    clerk_issuer_url: str = "https://deciding-redbird-5792.clerk.accounts.dev"
    clerk_authorized_party: str = "http://localhost:5173"
    janus_agent_api_key: str = ""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_production_settings(settings: Settings) -> None:
    if settings.app_env != "production":
        return
    problems: list[str] = []
    if settings.seed_demo_catalog:
        problems.append("demo catalog seeding must be disabled")
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        problems.append("PostgreSQL is required")
    if not settings.auth_required or not settings.clerk_issuer_url.startswith("https://"):
        problems.append("Clerk session verification is required")
    if not settings.clerk_authorized_party:
        problems.append("Clerk authorized party is required")
    if len(settings.janus_agent_api_key) < 32:
        problems.append("a 32+ character agent API key is required")
    if settings.razorpay_mode != "test" or not settings.razorpay_key_id.startswith("rzp_test_") or not settings.razorpay_key_secret:
        problems.append("Razorpay test credentials are required")
    if not (settings.gemini_api_key or settings.ai_gateway_api_key or settings.vercel_oidc_token or settings.llm_api_key):
        problems.append("a semantic model credential is required")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
