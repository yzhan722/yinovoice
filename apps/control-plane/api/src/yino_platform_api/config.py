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
    database_url: str | None = None
    recording_s3_endpoint: str | None = None
    recording_s3_bucket: str | None = None
    recording_s3_access_key: str | None = None
    recording_s3_secret_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

