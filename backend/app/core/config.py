from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = Field(default="development")
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)
    DEMO_MODE: bool = Field(default=False)

    DATABASE_URL: str = Field(default="sqlite:///./data/logs.db")
    SECRET_KEY: str = Field(default="development-session-encryption-secret-key-32chars")
    SESSION_COOKIE_NAME: str = Field(default="log_anomaly_session")
    CSRF_COOKIE_NAME: str = Field(default="csrf_token")

    OIDC_DISCOVERY_URL: str = Field(default="http://127.0.0.1:8080/realms/master/.well-known/openid-configuration")
    OIDC_CLIENT_ID: str = Field(default="log-anomaly-detector")
    OIDC_CLIENT_SECRET: str = Field(default="")
    OIDC_REDIRECT_URI: str = Field(default="http://127.0.0.1:8000/api/auth/callback")

    LLM_PROVIDER: str = Field(default="openai-compatible")
    LLM_BASE_URL: str = Field(default="https://llm.chris-vo.com/v1")
    LLM_MODEL: str = Field(default="qwen3.8-27b")
    LLM_API_KEY: str = Field(default="")

    @field_validator("DEMO_MODE")
    @classmethod
    def validate_demo(cls, v: bool, info) -> bool:
        if v and info.data.get("ENVIRONMENT", "development").lower() == "production":
            raise ValueError("DEMO_MODE refused in production.")
        return v

    def verify_runtime_safety(self) -> None:
        if self.DEMO_MODE and self.ENVIRONMENT.lower() == "production":
            raise RuntimeError("DEMO_MODE startup refused in production.")

settings = Settings()
