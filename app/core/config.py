from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # Database
    MONGODB_URL: str = Field(..., description="MongoDB connection URL")
    MONGODB_DB_NAME: str = Field(..., description="MongoDB database name")

    # AI API Keys
    GOOGLE_API_KEY: str = Field(..., description="Google API key for Gemini")
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")

    # AI Models
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash", description="Gemini model to use")

    # AWS
    AWS_REGION: str = Field(default="ca-central-1", description="AWS region")

    # Application
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=True, description="Debug mode")

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@lru_cache
def get_settings_no_cache() -> Settings:
    return Settings()  # type: ignore[call-arg]
