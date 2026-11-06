from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://thesis_user:thesis_password@localhost:5432/schedule_ai"
    JWT_SECRET: str = "super-secret-thesis-jwt-key-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # LLM-Agnostic Configuration: "ollama" or "openai_compatible"
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"  # Can be switched to "mistral"
    CLOUD_API_KEY: str = ""
    CLOUD_BASE_URL: str = "https://api.openai.com/v1"
    CLOUD_MODEL: str = "gpt-4o-mini"

settings = Settings()