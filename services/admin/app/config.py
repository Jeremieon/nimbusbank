from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # admin-service is the central request-log sink and ops-traffic API. Its
    # /ingest and /admin/traffic routes are unauthenticated on purpose (see the
    # LAB-ONLY note in main.py). /admin/overview requires a bearer JWT, so this
    # service still needs auth-service's JWKS to validate it — fetched lazily
    # (admin-service deliberately does NOT depend on auth at boot).
    auth_jwks_url: str = "http://auth:8000/.well-known/jwks.json"

    # Reserved for later phases (e.g. dialing rate limits up/down). Not yet
    # enforced anywhere in this codebase.
    security_level: str = "vulnerable"

    frontend_origin: str = "http://localhost:5173"
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
