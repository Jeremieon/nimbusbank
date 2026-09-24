from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    ssn_last4: str = Field(pattern=r"^\d{4}$")


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_verified: bool
    created_at: datetime


class RegisterResponse(BaseModel):
    user: UserOut
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    otp_required: bool
    user_id: str
    # LAB-ONLY: the OTP is echoed back in the response body so you don't need
    # a mail/SMS server to exercise the login flow. A real bank would send
    # this out-of-band and never put it in an API response.
    otp: str
    # If True, the user enrolled a real TOTP authenticator app and the
    # frontend should collect a 6-digit code and call /login/totp/verify
    # instead of the weak-OTP path. Both paths coexist.
    totp_enabled: bool = False


class OtpVerifyRequest(BaseModel):
    user_id: str
    otp: str = Field(pattern=r"^\d{4}$")


class TotpVerifyRequest(BaseModel):
    user_id: str
    code: str = Field(pattern=r"^\d{6}$")


class TotpConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class TotpEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_png_base64: str


class TotpStatusResponse(BaseModel):
    totp_enabled: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    user_id: str
    # LAB-ONLY: the reset token is echoed back in the response body so you can
    # exercise the reset flow without a mail server — exactly like the login
    # OTP. A real bank would send this out-of-band and never return it in an
    # API response.
    reset_token: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    # The API still accepts current_password so the shape is realistic, but
    # INTENTIONALLY VULNERABLE: the endpoint never verifies it (see main.py).
    current_password: str = ""
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    """INTENTIONALLY VULNERABLE: mass assignment. Every field is optional and
    there is NO allowlist of caller-settable fields — a plain customer can
    include privileged fields like `role`, `is_verified`, `email`, or
    `ssn_last4` and have them written straight onto their own user row (see
    main.py's PATCH /me). This is the marquee privilege-escalation gap."""

    full_name: str | None = None
    email: EmailStr | None = None
    ssn_last4: str | None = None
    role: str | None = None
    is_verified: bool | None = None
