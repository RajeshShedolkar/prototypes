"""Embedded Mock OAuth 2.0 Authorization & Resource Server.

Provides a fully compliant, self-contained OAuth 2.0 + PKCE provider for local testing
without needing external Google or GitHub API accounts.
"""

from __future__ import annotations
import hashlib
import json
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from oauth_core import compute_code_challenge


@dataclass
class AuthCodeEntry:
    code: str
    client_id: str
    redirect_uri: str
    code_challenge: Optional[str]
    code_challenge_method: Optional[str]
    scope: str
    created_at: float = field(default_factory=time.time)


@dataclass
class TokenEntry:
    access_token: str
    refresh_token: str
    client_id: str
    scope: str
    expires_at: float
    user_id: str


class MockOAuthServerState:
    """In-memory state store for the mock authorization server."""

    def __init__(self):
        self.valid_client_id = "mock-client-id-12345"
        self.valid_client_secret = "mock-client-secret-67890"
        self.auth_codes: Dict[str, AuthCodeEntry] = {}
        self.tokens: Dict[str, TokenEntry] = {}
        self.mock_user = {
            "id": "usr_dev_42",
            "name": "Grace Hopper",
            "email": "grace.hopper@example.com",
            "role": "Systems Architect",
            "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
            "bio": "Pioneer of computer programming and compiler development.",
        }

    def issue_auth_code(
        self,
        client_id: str,
        redirect_uri: str,
        code_challenge: Optional[str],
        code_challenge_method: Optional[str],
        scope: str,
    ) -> str:
        code = f"authcode_{secrets.token_hex(16)}"
        self.auth_codes[code] = AuthCodeEntry(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
        )
        return code

    def exchange_code(
        self,
        code: str,
        client_id: str,
        client_secret: Optional[str],
        redirect_uri: str,
        code_verifier: Optional[str],
    ) -> Tuple[int, Dict]:
        entry = self.auth_codes.get(code)
        if not entry:
            return 400, {"error": "invalid_grant", "error_description": "Authorization code is invalid or expired"}

        # Codes are single-use
        del self.auth_codes[code]

        # Verify client
        if entry.client_id != client_id:
            return 400, {"error": "invalid_client", "error_description": "Client ID mismatch"}

        # PKCE verification if challenge was registered
        if entry.code_challenge:
            if not code_verifier:
                return 400, {"error": "invalid_request", "error_description": "code_verifier required for PKCE"}
            expected_challenge = compute_code_challenge(code_verifier)
            if expected_challenge != entry.code_challenge:
                return 400, {
                    "error": "invalid_grant",
                    "error_description": "PKCE code_verifier does not match code_challenge",
                }

        # Issue tokens
        access_token = f"mock_at_{secrets.token_urlsafe(32)}"
        refresh_token = f"mock_rt_{secrets.token_urlsafe(32)}"
        expires_in = 3600  # 1 hour

        self.tokens[access_token] = TokenEntry(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            scope=entry.scope,
            expires_at=time.time() + expires_in,
            user_id=self.mock_user["id"],
        )

        return 200, {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token,
            "scope": entry.scope,
        }

    def refresh(self, refresh_token: str, client_id: str) -> Tuple[int, Dict]:
        match = next((t for t in self.tokens.values() if t.refresh_token == refresh_token), None)
        if not match:
            return 400, {"error": "invalid_grant", "error_description": "Invalid refresh token"}

        # Issue new access token
        new_access_token = f"mock_at_{secrets.token_urlsafe(32)}"
        expires_in = 3600
        self.tokens[new_access_token] = TokenEntry(
            access_token=new_access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            scope=match.scope,
            expires_at=time.time() + expires_in,
            user_id=match.user_id,
        )

        return 200, {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token,
            "scope": match.scope,
        }

    def get_user_profile(self, access_token: str) -> Tuple[int, Dict]:
        token_entry = self.tokens.get(access_token)
        if not token_entry:
            return 401, {"error": "invalid_token", "error_description": "Unknown or expired access token"}
        if time.time() > token_entry.expires_at:
            return 401, {"error": "invalid_token", "error_description": "Token has expired"}
        return 200, self.mock_user


# Singleton store for the mock server
mock_server_state = MockOAuthServerState()


def render_consent_page(
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    """Pure functional HTML renderer for the OAuth 2.0 Consent Screen."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mock OAuth 2.0 Consent Screen</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; width: 100%; max-width: 520px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h2 {{ margin-top: 0; color: #38bdf8; font-size: 1.5rem; }}
        p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }}
        .badge {{ background: #0369a1; color: #e0f2fe; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; display: inline-block; margin-bottom: 16px; }}
        .info-box {{ background: #0f172a; border-radius: 8px; padding: 14px; margin: 20px 0; font-family: monospace; font-size: 0.85rem; color: #cbd5e1; }}
        .info-row {{ display: flex; justify-content: space-between; margin-bottom: 6px; }}
        .info-label {{ color: #64748b; }}
        .btn {{ display: inline-block; width: 100%; padding: 12px; border-radius: 8px; font-weight: 600; font-size: 1rem; cursor: pointer; text-align: center; border: none; text-decoration: none; margin-top: 10px; box-sizing: border-box; }}
        .btn-authorize {{ background: #0284c7; color: white; }}
        .btn-authorize:hover {{ background: #0369a1; }}
        .btn-deny {{ background: transparent; color: #ef4444; border: 1px solid #ef4444; }}
        .btn-deny:hover {{ background: #ef444415; }}
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">Local Mock OAuth 2.0 Server</span>
        <h2>Authorize Application</h2>
        <p>The client application is requesting access to your mock identity and claims:</p>
        
        <div class="info-box">
            <div class="info-row"><span class="info-label">Client ID:</span> <span>{client_id}</span></div>
            <div class="info-row"><span class="info-label">Redirect URI:</span> <span>{redirect_uri}</span></div>
            <div class="info-row"><span class="info-label">Requested Scope:</span> <span>{scope}</span></div>
            <div class="info-row"><span class="info-label">PKCE Enabled:</span> <span>{"Yes (S256)" if code_challenge else "No"}</span></div>
        </div>

        <form method="POST" action="/mock-oauth/approve">
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="scope" value="{scope}">
            <input type="hidden" name="state" value="{state}">
            <input type="hidden" name="code_challenge" value="{code_challenge}">
            <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
            <button type="submit" name="action" value="allow" class="btn btn-authorize">Authorize Application</button>
            <button type="submit" name="action" value="deny" class="btn btn-deny">Deny</button>
        </form>
    </div>
</body>
</html>"""

