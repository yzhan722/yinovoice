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
    recording_s3_region: str | None = None
    phone_lookup_token: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    insights_base_url: str | None = None
    insights_ingest_token: str | None = None
    demo_operator_account: str = "demo"
    demo_operator_password: str = "demo123"
    demo_operator_tenant_id: str = "00000000-0000-0000-0000-000000000001"
    auth_secret: str | None = None

