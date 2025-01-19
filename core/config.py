from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, computed_field, model_validator
from typing_extensions import Self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="./.env",  # Ruta al archivo .env
        env_ignore_empty=True,
        extra="ignore",
    )

    # Configuración de base de datos
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5544
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Configuración de correos
    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_PASSWORD: str
    EMAILS_FROM_EMAIL: str

    # Otros parámetros
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    PROJECT_NAME: str
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    # FTP Configuración
    FTP_USER: str
    FTP_PASSWORD: str
    FTP_SERVER: str
    BACKEND_URL:str

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY is not set!")
        if not self.SMTP_HOST:
            raise ValueError("SMTP_HOST is required!")
        return self


settings = Settings()