"""Pure Functional Core for OAuth 2.0 with PKCE (RFC 7636 and RFC 6749).

This module contains pure mathematical and transformation functions with NO I/O,
ensuring determinism, full testability, and zero side effects.
"""

from __future__ import annotations
import base64
import hashlib
import hmac
import secrets
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union

from config import OAuthConfig

T = TypeVar("T")
E = TypeVar("E")


# ============================================================================
# Functional Result Monad / Either Type for Explicit Error Handling
# ============================================================================

@dataclass(frozen=True)
class Success(Generic[T]):
    """Represents a successful outcome holding a value."""
    value: T
    is_success: bool = True

    def map(self, func: Callable[[T], Any]) -> Result:
        return Success(func(self.value))

    def bind(self, func: Callable[[T], Result]) -> Result:
        return func(self.value)


@dataclass(frozen=True)
class Failure(Generic[E]):
    """Represents a failed outcome holding an error description."""
    error: E
    is_success: bool = False

    def map(self, func: Callable[[Any], Any]) -> Result:
        return self

    def bind(self, func: Callable[[Any], Result]) -> Result:
        return self


Result = Union[Success[T], Failure[E]]


# ============================================================================
# Functional Composition Utilities
# ============================================================================

def pipe(initial_value: Any, *functions: Callable[[Any], Any]) -> Any:
    """Pipelines an initial value through a series of pure functions.
    
    Equivalent to F# / Elixir / Unix pipe operator: value |> f |> g |> h.
    """
    current = initial_value
    for func in functions:
        current = func(current)
    return current


# ============================================================================
# Immutable OAuth Data Structures
# ============================================================================

@dataclass(frozen=True)
class PKCEPair:
    """RFC 7636 Proof Key for Code Exchange pair."""
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


@dataclass(frozen=True)
class OAuthState:
    """Immutable state tracking a pending authorization request."""
    state: str
    pkce: Optional[PKCEPair]
    provider: str


@dataclass(frozen=True)
class TokenResponse:
    """Immutable parsed OAuth 2.0 Token Response."""
    access_token: str
    token_type: str
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class UserProfile:
    """Normalized immutable user identity retrieved from the resource server."""
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    provider: str = ""
    raw_claims: Optional[Dict[str, Any]] = None


# ============================================================================
# Pure Cryptographic & Token Functions
# ============================================================================

def compute_code_challenge(verifier: str) -> str:
    """Computes code_challenge from code_verifier according to RFC 7636.
    
    code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier))) without padding.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def generate_pkce_pair(random_bytes_provider: Callable[[int], bytes] = secrets.token_bytes) -> PKCEPair:
    """Pure factory that generates a high-entropy PKCE verifier and challenge.
    
    Code verifier is 43-128 unreserved URL characters. 32 bytes base64url-encoded produces 43 chars.
    """
    raw_bytes = random_bytes_provider(32)
    verifier = base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")
    challenge = compute_code_challenge(verifier)
    return PKCEPair(
        code_verifier=verifier,
        code_challenge=challenge,
        code_challenge_method="S256",
    )


def generate_secure_state(random_bytes_provider: Callable[[int], bytes] = secrets.token_bytes) -> str:
    """Generates a cryptographically secure random state parameter for CSRF mitigation."""
    return base64.urlsafe_b64encode(random_bytes_provider(24)).decode("ascii").rstrip("=")


def verify_state(expected_state: str, received_state: str) -> bool:
    """Constant-time comparison of state parameters to prevent CSRF and timing attacks."""
    if not expected_state or not received_state:
        return False
    return hmac.compare_digest(expected_state, received_state)


# ============================================================================
# Pure URL & Request Transformation Functions
# ============================================================================

def build_authorization_url(
    config: OAuthConfig,
    state: str,
    pkce: Optional[PKCEPair] = None,
    extra_params: Optional[Dict[str, str]] = None,
) -> str:
    """Pure function to construct the OAuth 2.0 Authorization URL with query parameters."""
    params: Dict[str, str] = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope_string,
        "state": state,
    }

    if pkce and config.supports_pkce:
        params["code_challenge"] = pkce.code_challenge
        params["code_challenge_method"] = pkce.code_challenge_method

    if extra_params:
        params.update(extra_params)

    query_string = urllib.parse.urlencode(params)
    separator = "&" if "?" in config.authorize_endpoint else "?"
    return f"{config.authorize_endpoint}{separator}{query_string}"


def build_token_request_body(
    config: OAuthConfig,
    code: str,
    code_verifier: Optional[str] = None,
) -> Dict[str, str]:
    """Pure function preparing the application/x-www-form-urlencoded POST body for token exchange."""
    body: Dict[str, str] = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "code": code,
        "redirect_uri": config.redirect_uri,
    }
    if config.client_secret:
        body["client_secret"] = config.client_secret
    if code_verifier and config.supports_pkce:
        body["code_verifier"] = code_verifier
    return body


def build_refresh_token_request_body(
    config: OAuthConfig,
    refresh_token: str,
) -> Dict[str, str]:
    """Pure function preparing the POST body to refresh an expired access token."""
    body: Dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": config.client_id,
        "refresh_token": refresh_token,
    }
    if config.client_secret:
        body["client_secret"] = config.client_secret
    return body


# ============================================================================
# Pure Response Parsers
# ============================================================================

def parse_token_response(payload: Dict[str, Any]) -> Result[TokenResponse, str]:
    """Pure parser converting raw provider JSON or dictionary into TokenResponse."""
    if "error" in payload:
        error_desc = payload.get("error_description", payload["error"])
        return Failure(f"OAuth Provider Error: {error_desc}")

    access_token = payload.get("access_token")
    if not access_token:
        return Failure("Invalid token response: 'access_token' missing")

    token_type = payload.get("token_type", "Bearer")
    expires_in = payload.get("expires_in")
    if expires_in is not None:
        try:
            expires_in = int(expires_in)
        except (ValueError, TypeError):
            expires_in = None

    return Success(
        TokenResponse(
            access_token=access_token,
            token_type=token_type,
            expires_in=expires_in,
            refresh_token=payload.get("refresh_token"),
            scope=payload.get("scope"),
            id_token=payload.get("id_token"),
            raw_payload=payload,
        )
    )


def parse_user_profile(payload: Dict[str, Any], provider_name: str) -> UserProfile:
    """Pure normalizer mapping vendor-specific user claims to a unified UserProfile."""
    # GitHub schema: 'id', 'login', 'name', 'email', 'avatar_url'
    # Google schema: 'sub', 'name', 'email', 'picture'
    # Mock schema: 'id', 'name', 'email', 'avatar_url'
    user_id = str(payload.get("id") or payload.get("sub") or "")
    name = str(payload.get("name") or payload.get("login") or payload.get("email") or "Unknown User")
    email = str(payload.get("email") or "")
    avatar = payload.get("avatar_url") or payload.get("picture")

    return UserProfile(
        id=user_id,
        name=name,
        email=email,
        avatar_url=str(avatar) if avatar else None,
        provider=provider_name,
        raw_claims=payload,
    )
