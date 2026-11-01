"""OAuth 2.0 Configuration module.

Defines immutable configuration models and pre-configured provider presets
using functional programming concepts (frozen dataclasses, pure constructors).
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


def load_env_file() -> None:
    """Lightweight zero-dependency .env loader."""
    candidate_paths = [
        Path(".env"),
        Path(__file__).parent / ".env",
    ]
    for env_path in candidate_paths:
        if env_path.is_file():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("\"'")
                        if key:
                            os.environ[key] = val
                break
            except Exception:
                pass


load_env_file()


@dataclass(frozen=True)
class OAuthConfig:
    """Immutable configuration for an OAuth 2.0 Authorization Server."""
    name: str
    client_id: str
    client_secret: str
    authorize_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    redirect_uri: str
    scopes: Tuple[str, ...]
    supports_pkce: bool = True

    @property
    def scope_string(self) -> str:
        """Space-separated scopes string."""
        return " ".join(self.scopes)


def create_mock_config(base_url: str = "http://localhost:8000") -> OAuthConfig:
    """Pure factory for the built-in local Mock OAuth Provider."""
    return OAuthConfig(
        name="Mock Provider (Local)",
        client_id="mock-client-id-12345",
        client_secret="mock-client-secret-67890",
        authorize_endpoint=f"{base_url}/mock-oauth/authorize",
        token_endpoint=f"{base_url}/mock-oauth/token",
        userinfo_endpoint=f"{base_url}/mock-oauth/userinfo",
        redirect_uri=f"{base_url}/callback",
        scopes=("read:profile", "read:email"),
        supports_pkce=True,
    )


def create_github_config(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    redirect_uri: str = "http://localhost:8000/callback",
) -> OAuthConfig:
    """Pure factory for GitHub OAuth 2.0 Provider."""
    return OAuthConfig(
        name="GitHub",
        client_id=client_id or os.getenv("GITHUB_CLIENT_ID", ""),
        client_secret=client_secret or os.getenv("GITHUB_CLIENT_SECRET", ""),
        authorize_endpoint="https://github.com/login/oauth/authorize",
        token_endpoint="https://github.com/login/oauth/access_token",
        userinfo_endpoint="https://api.github.com/user",
        redirect_uri=redirect_uri,
        scopes=("read:user", "user:email"),
        supports_pkce=False,  # GitHub web application flow traditionally uses client_secret
    )


def create_google_config(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    redirect_uri: str = "http://localhost:8000/callback",
) -> OAuthConfig:
    """Pure factory for Google OAuth 2.0 / OpenID Connect Provider."""
    return OAuthConfig(
        name="Google",
        client_id=client_id or os.getenv("GOOGLE_CLIENT_ID", ""),
        client_secret=client_secret or os.getenv("GOOGLE_CLIENT_SECRET", ""),
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        redirect_uri=redirect_uri,
        scopes=("openid", "email", "profile"),
        supports_pkce=True,
    )
