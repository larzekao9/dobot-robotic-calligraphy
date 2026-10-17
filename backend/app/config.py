from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./nombres.db"
    admin_token: str = ""  # vacío = administración y robot sin contraseña
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    rate_limit_per_minute: int = 30
    robot_driver: str = "mock"  # "dobot" llega en la Fase 2
    mock_time_scale: float = 10.0  # el simulador va N veces más rápido que el robot real
    robot_config_path: str = ""  # por defecto: data/robot_config.json


settings = Settings()
