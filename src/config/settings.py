from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Raised when a live service is used without complete configuration."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_search_model: str = "deepseek-v4-flash"
    semantic_retrieval_enabled: bool = True
    semantic_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    semantic_reranker_model: str = "BAAI/bge-reranker-base"
    demo_rate_limit_per_minute: int = Field(default=12, ge=0, le=120)

    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: SecretStr | None = None
    neo4j_database: str = "neo4j"

    def require_deepseek(self) -> None:
        if not self.deepseek_api_key or not self.deepseek_api_key.get_secret_value():
            raise ConfigurationError(
                "DEEPSEEK_API_KEY is missing. Copy .env.example to .env and add a valid key."
            )

    def require_neo4j(self) -> None:
        missing = []
        if not self.neo4j_uri:
            missing.append("NEO4J_URI")
        if not self.neo4j_username:
            missing.append("NEO4J_USERNAME")
        if not self.neo4j_password or not self.neo4j_password.get_secret_value():
            missing.append("NEO4J_PASSWORD")
        if missing:
            raise ConfigurationError(
                f"Missing Neo4j configuration: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in the Aura credentials."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
