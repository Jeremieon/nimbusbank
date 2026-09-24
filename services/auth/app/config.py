from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # auth-service is the only service that holds the RS256 private key.
    # Both files are generated on first startup if missing (see security.py)
    # and persisted under the /keys volume so tokens stay valid across
    # container restarts.
    jwt_private_key_path: str = "/keys/private.pem"
    jwt_public_key_path: str = "/keys/public.pem"
    jwt_key_id: str = "nimbusbank-key-1"

    jwt_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    otp_expire_minutes: int = 5

    # Where this service fires its fire-and-forget request-log events. Points
    # at admin-service's internal ingest sink over the docker network. If admin
    # is down the log POST is swallowed and the real request is unaffected
    # (see obslog.py).
    admin_ingest_url: str = "http://admin:8000/ingest"

    # Reserved for later phases (e.g. dialing rate limits up/down). Not yet
    # enforced anywhere in this codebase.
    security_level: str = "vulnerable"

    frontend_origin: str = "http://localhost:5173"
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
