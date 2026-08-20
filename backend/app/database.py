from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Settings(BaseSettings):
    database_url: str

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
    )


settings = Settings()

engine = create_engine(
    settings.database_url,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()