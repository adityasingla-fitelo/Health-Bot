from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "GenZ Health Bot"
    DATABASE_URL: str
    OPENAI_API_KEY: str
    JWT_SECRET: str
    JWT_ALGO: str = "HS256"

    class Config:
        env_file = ".env"

settings = Settings()
