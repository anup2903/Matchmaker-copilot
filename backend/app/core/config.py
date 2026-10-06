from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://matchmaker:matchmaker@localhost:5432/matchmaker"
    cors_origins: str = "http://localhost:3000"

    # LLM — any OpenAI-compatible chat-completions provider. Model is never hard-coded.
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = 30.0
    # Mirror phrasing is best-effort cosmetic wording; keep its wait short so a slow free-tier response
    # falls back to the deterministic template instead of stalling a page.
    llm_phrase_timeout_seconds: float = 8.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip() and self.llm_model.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
