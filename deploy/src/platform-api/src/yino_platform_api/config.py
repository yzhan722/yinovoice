from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        extra="ignore",
    )

    livekit_url: str = "ws://localhost:7880"
    livekit_api_url: str = "http://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    livekit_agent_name: str = "yino-customer-service"
    call_recording_dir: str = "data/recordings"
    call_recording_max_bytes: int = 104_857_600
    # CORS origins as comma-separated string in env (e.g. "https://8.215.80.82,http://localhost:3003")
    # Parsed into a list for Starlette CORSMiddleware.
    cors_origins: list[str] = ["http://localhost:3003", "http://localhost:5173"]
