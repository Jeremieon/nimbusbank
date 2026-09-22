import base64
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Header, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Populated by ensure_keys() at startup, then held in memory for the life of
# the process.
_private_key_pem: bytes | None = None
_public_key_pem: bytes | None = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def ensure_keys() -> None:
    """Load the RSA keypair from the /keys volume, generating a fresh
    2048-bit pair on first boot if the files aren't there yet. auth-service
    is the only service that ever touches the private key — accounts and
    transfers only ever see the public half, via /.well-known/jwks.json."""
    global _private_key_pem, _public_key_pem

    os.makedirs(os.path.dirname(settings.jwt_private_key_path), exist_ok=True)

    if os.path.exists(settings.jwt_private_key_path) and os.path.exists(settings.jwt_public_key_path):
        with open(settings.jwt_private_key_path, "rb") as f:
            _private_key_pem = f.read()
        with open(settings.jwt_public_key_path, "rb") as f:
            _public_key_pem = f.read()
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    with open(settings.jwt_private_key_path, "wb") as f:
        f.write(private_pem)
    with open(settings.jwt_public_key_path, "wb") as f:
        f.write(public_pem)

    _private_key_pem = private_pem
    _public_key_pem = public_pem


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def get_jwks() -> dict:
    """Public key only, as a JWK — this is what accounts-service and
    transfers-service fetch over the docker network to validate access
    tokens themselves, and it's the literal input to F5 XC's JWT validation
    feature at the edge."""
    public_key = serialization.load_pem_public_key(_public_key_pem)
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": settings.jwt_key_id,
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


def create_access_token(*, user_id: str, role: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "type": "access",
    }
    return jwt.encode(claims, _private_key_pem, algorithm="RS256", headers={"kid": settings.jwt_key_id})


def create_refresh_token(*, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_expire_days),
        "type": "refresh",
    }
    return jwt.encode(claims, _private_key_pem, algorithm="RS256", headers={"kid": settings.jwt_key_id})


def decode_token(token: str, *, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, _public_key_pem, algorithms=["RS256"])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Wrong token type")
    return payload


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Validates the bearer access token against our own public key. This is
    the same check accounts-service and transfers-service perform against
    our JWKS endpoint — kept here too so auth-service's own /me route
    doesn't need a network round trip to itself."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token, expected_type="access")
    return {"user_id": payload["sub"], "role": payload.get("role"), "email": payload.get("email")}
