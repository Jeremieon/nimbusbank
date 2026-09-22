from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    # transfers-service holds no signing key of its own — it fetches
    # auth-service's public JWKS over the internal docker network and
    # validates bearer tokens against that. This mirrors how F5 XC itself
    # validates JWTs at the edge against a JWKS URL.
    auth_jwks_url: str = "http://auth:8000/.well-known/jwks.json"

    # Reserved for later phases (e.g. dialing rate limits up/down). Not yet
    # enforced anywhere in this codebase.
    security_level: str = "vulnerable"

    frontend_origin: str = "http://localhost:5173"
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
