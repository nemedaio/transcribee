from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel, ValidationError

from lnkdn_transcripts.config import Settings
from lnkdn_transcripts.logging import get_logger

try:
    from authlib.integrations.starlette_client import OAuth
except ImportError:  # pragma: no cover - exercised through configuration checks
    OAuth = None

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
PUBLIC_PATH_PREFIXES = ("/static/", "/health", "/auth/")

logger = get_logger(__name__)


class GoogleAuthConfigurationError(RuntimeError):
    pass


class UnauthorizedGoogleAccountError(RuntimeError):
    pass


class AuthenticatedUser(BaseModel):
    email: str
    name: str | None = None
    picture: str | None = None
    hosted_domain: str | None = None


class GoogleAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._oauth = None
        if not settings.auth_enabled:
            return

        if not settings.session_secret_key:
            raise GoogleAuthConfigurationError("Session secret key is required when auth is enabled")

        if OAuth is None:
            raise GoogleAuthConfigurationError("Authlib must be installed to enable Google auth")

        if not settings.auth_test_mode and (
            not settings.google_client_id or not settings.google_client_secret
        ):
            raise GoogleAuthConfigurationError(
                "Google client id and secret are required when auth is enabled"
            )

        if settings.google_client_id and settings.google_client_secret:
            oauth = OAuth()
            oauth.register(
                name="google",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                server_metadata_url=GOOGLE_DISCOVERY_URL,
                client_kwargs={"scope": "openid email profile"},
            )
            self._oauth = oauth

    @property
    def is_enabled(self) -> bool:
        return self.settings.auth_enabled

    @property
    def allowed_email_domains(self) -> set[str]:
        if not self.settings.google_allowed_email_domains:
            return set()
        return {
            domain.strip().lower()
            for domain in self.settings.google_allowed_email_domains.split(",")
            if domain.strip()
        }

    def requires_auth(self, path: str) -> bool:
        if not self.is_enabled:
            return False
        return not any(path == prefix or path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)

    def current_user(self, request: Request) -> AuthenticatedUser | None:
        if not self.is_enabled:
            return None
        try:
            payload = request.session.get("user")
        except AssertionError:
            return None
        if not payload:
            return None
        try:
            return AuthenticatedUser.model_validate(payload)
        except ValidationError:
            logger.warning("auth.session.invalid_payload")
            request.session.pop("user", None)
            return None

    def build_login_context(self, next_url: str, error_message: str | None = None) -> dict:
        return {
            "page_title": "Sign in",
            "next_url": self.normalize_next_url(next_url),
            "error_message": error_message,
            "allowed_email_domains": sorted(self.allowed_email_domains),
        }

    def normalize_next_url(self, next_url: str | None) -> str:
        if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
            return "/"
        return next_url

    async def begin_google_login(self, request: Request, next_url: str) -> object:
        if self._oauth is None:
            raise GoogleAuthConfigurationError(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            )
        request.session["auth_next"] = self.normalize_next_url(next_url)
        logger.info("auth.google.begin next=%s", request.session["auth_next"])
        authorize_kwargs = {"prompt": "select_account"}
        allowed_domains = sorted(self.allowed_email_domains)
        if len(allowed_domains) == 1:
            authorize_kwargs["hd"] = allowed_domains[0]
        return await self._oauth.google.authorize_redirect(
            request,
            request.url_for("auth_callback"),
            **authorize_kwargs,
        )

    async def complete_google_login(self, request: Request) -> AuthenticatedUser:
        if self._oauth is None:
            raise GoogleAuthConfigurationError(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            )

        token = await self._oauth.google.authorize_access_token(request)
        payload = token.get("userinfo")
        if payload is None:
            payload = await self._oauth.google.userinfo(token=token)
        user = self._validate_google_user(payload)
        request.session["user"] = user.model_dump()
        logger.info("auth.google.success email=%s", user.email)
        return user

    def logout(self, request: Request) -> None:
        email = None
        current_user = self.current_user(request)
        if current_user is not None:
            email = current_user.email
        request.session.pop("user", None)
        request.session.pop("auth_next", None)
        logger.info("auth.logout email=%s", email or "anonymous")

    def test_login(self, request: Request, email: str, name: str | None = None) -> AuthenticatedUser:
        if not self.settings.auth_test_mode:
            raise GoogleAuthConfigurationError("Test login is only available in auth test mode")
        user = self._validate_google_user(
            {
                "email": email,
                "email_verified": True,
                "name": name or email.split("@", 1)[0],
            }
        )
        request.session["user"] = user.model_dump()
        logger.info("auth.test_login email=%s", user.email)
        return user

    def consume_next_url(self, request: Request, fallback: str = "/") -> str:
        next_url = request.session.pop("auth_next", None) or fallback
        return self.normalize_next_url(next_url)

    def _validate_google_user(self, payload: dict) -> AuthenticatedUser:
        email = str(payload.get("email") or "").strip().lower()
        if not email:
            raise UnauthorizedGoogleAccountError("Google did not return an email address")
        if payload.get("email_verified") is False:
            raise UnauthorizedGoogleAccountError("Only verified Google accounts can sign in")

        domain = email.rsplit("@", 1)[-1]
        allowed_domains = self.allowed_email_domains
        if allowed_domains and domain not in allowed_domains:
            raise UnauthorizedGoogleAccountError(
                f"Only Google accounts from {', '.join(sorted(allowed_domains))} can sign in"
            )

        return AuthenticatedUser(
            email=email,
            name=payload.get("name"),
            picture=payload.get("picture"),
            hosted_domain=payload.get("hd"),
        )
