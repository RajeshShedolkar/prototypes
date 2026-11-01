"""Functional HTTP Client for OAuth 2.0.

Isolates external network I/O from pure business logic using the Python standard library
(zero external dependencies) and returns immutable Result types.
"""

from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from config import OAuthConfig
from oauth_core import (
    Failure,
    Result,
    Success,
    TokenResponse,
    UserProfile,
    build_refresh_token_request_body,
    build_token_request_body,
    parse_token_response,
    parse_user_profile,
)


def _execute_http(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    form_data: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Result[Dict[str, Any], str]:
    """Purely functional wrapper around urllib execution returning Result monad."""
    req_headers = {
        "User-Agent": "Python-OAuth-Functional-Demo/1.0",
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)

    encoded_data: Optional[bytes] = None
    if form_data is not None:
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        encoded_data = urllib.parse.urlencode(form_data).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=encoded_data,
        headers=req_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw_body = response.read().decode("utf-8")

            # Try parsing as JSON first
            if "application/json" in content_type or raw_body.strip().startswith("{"):
                try:
                    parsed = json.loads(raw_body)
                    return Success(parsed)
                except json.JSONDecodeError as err:
                    return Failure(f"JSON decode failed: {err}")

            # Fallback for providers like GitHub that may return x-www-form-urlencoded
            parsed_form = urllib.parse.parse_qs(raw_body)
            if parsed_form:
                flattened = {k: v[0] for k, v in parsed_form.items()}
                return Success(flattened)

            return Failure(f"Unrecognized response format (status {status}): {raw_body[:200]}")

    except urllib.error.HTTPError as err:
        try:
            error_body = err.read().decode("utf-8")
            err_json = json.loads(error_body)
            msg = err_json.get("error_description") or err_json.get("error") or error_body
        except Exception:
            msg = str(err)
        return Failure(f"HTTP {err.code}: {msg}")
    except urllib.error.URLError as err:
        return Failure(f"Network error connecting to {url}: {err.reason}")
    except Exception as err:
        return Failure(f"Unexpected request error: {err}")


def exchange_code_for_token(
    config: OAuthConfig,
    code: str,
    code_verifier: Optional[str] = None,
) -> Result[TokenResponse, str]:
    """Exchanges an authorization code for access and refresh tokens."""
    payload = build_token_request_body(config, code, code_verifier)
    http_result = _execute_http(
        url=config.token_endpoint,
        method="POST",
        form_data=payload,
    )

    if not http_result.is_success:
        return Failure(http_result.error)

    return parse_token_response(http_result.value)


def refresh_access_token(
    config: OAuthConfig,
    refresh_token: str,
) -> Result[TokenResponse, str]:
    """Exchanges a refresh token for a fresh access token."""
    payload = build_refresh_token_request_body(config, refresh_token)
    http_result = _execute_http(
        url=config.token_endpoint,
        method="POST",
        form_data=payload,
    )

    if not http_result.is_success:
        return Failure(http_result.error)

    return parse_token_response(http_result.value)


def fetch_user_profile(
    config: OAuthConfig,
    token: TokenResponse,
) -> Result[UserProfile, str]:
    """Fetches the user profile from the resource server using Bearer authorization."""
    headers = {
        "Authorization": f"{token.token_type} {token.access_token}",
    }
    http_result = _execute_http(
        url=config.userinfo_endpoint,
        method="GET",
        headers=headers,
    )

    if not http_result.is_success:
        return Failure(http_result.error)

    profile = parse_user_profile(http_result.value, config.name)
    return Success(profile)

