"""Functional Web Application for OAuth 2.0 Prototype.

Zero external dependencies - runs directly on Python 3.9+ standard library.
Demonstrates functional routing, immutable state transformations, and unified
handling of both client-side OAuth and the embedded mock server.
"""

from __future__ import annotations
import http.cookies
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

from config import (
    OAuthConfig,
    create_github_config,
    create_google_config,
    create_mock_config,
    load_env_file,
)
from mock_server import mock_server_state, render_consent_page
from oauth_client import exchange_code_for_token, fetch_user_profile, refresh_access_token
from oauth_core import (
    Failure,
    OAuthState,
    PKCEPair,
    Success,
    TokenResponse,
    UserProfile,
    build_authorization_url,
    generate_pkce_pair,
    generate_secure_state,
    verify_state,
)

PORT = int(os.getenv("PORT", "8000"))
BASE_URL = f"http://localhost:{PORT}"

# In-memory store for client session states (keyed by session_id cookie)
client_sessions: Dict[str, Dict[str, Any]] = {}


def get_provider_config(provider_key: str) -> OAuthConfig:
    """Pure mapping from provider key to immutable OAuthConfig."""
    load_env_file()  # Refresh environment variables from .env
    if provider_key == "github":
        return create_github_config(redirect_uri=f"{BASE_URL}/callback")
    elif provider_key == "google":
        return create_google_config(redirect_uri=f"{BASE_URL}/callback")
    return create_mock_config(base_url=BASE_URL)


# ============================================================================
# Functional HTML View Renderers
# ============================================================================

def render_home_page(session: Dict[str, Any], message: str = "", error: str = "") -> str:
    """Pure functional HTML renderer for the OAuth Client Dashboard."""
    profile: Optional[UserProfile] = session.get("profile")
    token: Optional[TokenResponse] = session.get("token")
    provider_name: str = session.get("provider", "mock")

    notification_html = ""
    if error:
        notification_html = f'<div class="alert alert-danger">{error}</div>'
    elif message:
        notification_html = f'<div class="alert alert-success">{message}</div>'

    if profile and token:
        user_card_html = f"""
        <div class="card logged-in">
            <div class="user-header">
                <img src="{profile.avatar_url or 'https://api.dicebear.com/7.x/identicon/svg?seed=' + profile.id}" class="avatar" alt="Avatar">
                <div>
                    <h3>{profile.name}</h3>
                    <p class="subtitle">{profile.email or 'No public email'} &bull; Provider: <strong>{profile.provider}</strong></p>
                </div>
            </div>
            
            <div class="section-title">OAuth 2.0 Credentials Acquired</div>
            <div class="code-box">
                <div class="code-row"><span class="code-key">Access Token:</span> <span class="code-val">{token.access_token[:28]}...</span></div>
                <div class="code-row"><span class="code-key">Token Type:</span> <span class="code-val">{token.token_type}</span></div>
                <div class="code-row"><span class="code-key">Expires In:</span> <span class="code-val">{token.expires_in or 'N/A'} seconds</span></div>
                <div class="code-row"><span class="code-key">Refresh Token:</span> <span class="code-val">{token.refresh_token[:28] if token.refresh_token else 'None'}...</span></div>
                <div class="code-row"><span class="code-key">Scope:</span> <span class="code-val">{token.scope or 'default'}</span></div>
            </div>

            <div class="button-group">
                {'<form method="POST" action="/refresh" style="display:inline;"><button type="submit" class="btn btn-secondary">Refresh Access Token</button></form>' if token.refresh_token else ''}
                <form method="POST" action="/logout" style="display:inline;"><button type="submit" class="btn btn-danger">Log Out</button></form>
            </div>
        </div>
        """
    else:
        user_card_html = f"""
        <div class="card">
            <h3>Start OAuth 2.0 Authorization Code Flow</h3>
            <p class="text-muted">Select a provider to initiate the cryptographic PKCE exchange:</p>

            <div class="provider-options">
                <a href="/login?provider=mock" class="provider-btn mock-btn">
                    <strong>Local Mock Provider</strong>
                    <span>(Zero config &bull; PKCE S256 enabled &bull; Ready to run)</span>
                </a>
                <a href="/login?provider=github" class="provider-btn github-btn">
                    <strong>GitHub OAuth</strong>
                    <span>(Requires GITHUB_CLIENT_ID & GITHUB_CLIENT_SECRET)</span>
                </a>
                <a href="/login?provider=google" class="provider-btn google-btn">
                    <strong>Google OIDC</strong>
                    <span>(Requires GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET)</span>
                </a>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OAuth 2.0 + PKCE Functional Prototype</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #131b2e;
            --border: #1e293b;
            --text: #f1f5f9;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --success: #10b981;
            --danger: #ef4444;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 800px;
        }}
        header {{
            text-align: center;
            margin-bottom: 32px;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 8px;
            color: #fff;
            letter-spacing: -0.5px;
        }}
        .header-desc {{
            color: var(--muted);
            font-size: 1.05rem;
            margin: 0;
        }}
        .pipeline {{
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
            background: #080c14;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid var(--border);
            font-size: 0.8rem;
            justify-content: space-between;
            overflow-x: auto;
        }}
        .pipeline-step {{
            color: var(--muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .pipeline-step.active {{
            color: var(--accent);
            font-weight: 600;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        .alert {{
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
        }}
        .alert-success {{ background: #064e3b; color: #a7f3d0; border: 1px solid #059669; }}
        .alert-danger {{ background: #450a0a; color: #fecaca; border: 1px solid #dc2626; }}
        .user-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }}
        .avatar {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            border: 2px solid var(--accent);
            object-fit: cover;
        }}
        .subtitle {{
            color: var(--muted);
            margin: 4px 0 0 0;
            font-size: 0.9rem;
        }}
        .section-title {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
            margin: 16px 0 8px 0;
            font-weight: 600;
        }}
        .code-box {{
            background: #080c14;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 16px;
            font-family: ui-monospace, Menlo, Monaco, monospace;
            font-size: 0.85rem;
            margin-bottom: 20px;
        }}
        .code-row {{
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid #131b2e;
        }}
        .code-row:last-child {{ border-bottom: none; }}
        .code-key {{ color: #7dd3fc; }}
        .code-val {{ color: #cbd5e1; }}
        .provider-options {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 16px;
        }}
        .provider-btn {{
            display: flex;
            flex-direction: column;
            padding: 14px 18px;
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.2s;
            border: 1px solid var(--border);
        }}
        .mock-btn {{ background: #0284c7; color: white; border-color: #38bdf8; }}
        .mock-btn:hover {{ background: #0369a1; transform: translateY(-1px); }}
        .github-btn {{ background: #1e293b; color: white; }}
        .github-btn:hover {{ background: #334155; transform: translateY(-1px); }}
        .google-btn {{ background: #1e293b; color: white; }}
        .google-btn:hover {{ background: #334155; transform: translateY(-1px); }}
        .provider-btn span {{ font-size: 0.8rem; opacity: 0.85; margin-top: 4px; }}
        .btn {{
            padding: 10px 18px;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: background 0.2s;
        }}
        .btn-secondary {{ background: #334155; color: white; margin-right: 10px; }}
        .btn-secondary:hover {{ background: #475569; }}
        .btn-danger {{ background: #dc2626; color: white; }}
        .btn-danger:hover {{ background: #b91c1c; }}
        .button-group {{ display: flex; align-items: center; }}
        .info-card {{
            background: #080c14;
            border: 1px dashed var(--border);
            border-radius: 8px;
            padding: 16px;
            font-size: 0.85rem;
            color: var(--muted);
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>OAuth 2.0 + PKCE Prototype</h1>
            <p class="header-desc">Functional Python implementation of RFC 6749 &amp; RFC 7636</p>
        </header>

        <div class="pipeline">
            <span class="pipeline-step {'active' if not profile else ''}">1. PKCE &amp; State</span>
            <span>&rarr;</span>
            <span class="pipeline-step {'active' if not profile else ''}">2. Authorization</span>
            <span>&rarr;</span>
            <span class="pipeline-step">3. Callback Redirect</span>
            <span>&rarr;</span>
            <span class="pipeline-step {'active' if profile else ''}">4. Token Exchange</span>
            <span>&rarr;</span>
            <span class="pipeline-step {'active' if profile else ''}">5. Resource Access</span>
        </div>

        {notification_html}
        {user_card_html}

        <div class="info-card">
            <strong>Functional Architecture:</strong>
            Pure functions (in <code>oauth_core.py</code>) handle PKCE SHA-256 math, CSRF state verification, and URL transformations without side effects. External network I/O is cleanly isolated in <code>oauth_client.py</code> using immutable <code>Result[T, E]</code> monads.
        </div>
    </div>
</body>
</html>"""


# ============================================================================
# HTTP Request Handler
# ============================================================================

class FunctionalOAuthHandler(BaseHTTPRequestHandler):
    """Custom HTTP handler bridging standard library requests with functional pipeline."""

    def _get_or_create_session(self) -> Tuple[str, Dict[str, Any]]:
        cookie_header = self.headers.get("Cookie", "")
        cookies = http.cookies.SimpleCookie(cookie_header)
        session_id = cookies.get("session_id").value if "session_id" in cookies else None

        if not session_id or session_id not in client_sessions:
            session_id = generate_secure_state()
            client_sessions[session_id] = {}

        return session_id, client_sessions[session_id]

    def _send_html(self, content: str, status: int = 200, session_id: Optional[str] = None):
        body_bytes = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        if session_id:
            self.send_header("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_json(self, data: Any, status: int = 200):
        body_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _redirect(self, location: str, session_id: Optional[str] = None):
        self.send_response(302)
        self.send_header("Location", location)
        if session_id:
            self.send_header("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()

    def _read_body_form(self) -> Dict[str, str]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        parsed = urllib.parse.parse_qs(raw)
        return {k: v[0] for k, v in parsed.items()}

    # ------------------------------------------------------------------------
    # GET Routes
    # ------------------------------------------------------------------------
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed_url.query).items()}

        session_id, session = self._get_or_create_session()

        # 1. Home Dashboard
        if path == "/":
            msg = params.get("msg", "")
            err = params.get("err", "")
            html = render_home_page(session, message=msg, error=err)
            self._send_html(html, session_id=session_id)

        # 2. Start OAuth Flow
        elif path == "/login":
            provider_key = params.get("provider", "mock")
            config = get_provider_config(provider_key)

            if not config.client_id:
                if provider_key == "google":
                    err_msg = (
                        "Google credentials missing! Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET "
                        "to your prototypes/Oauth2.0/.env file, or export them in your shell. "
                        "(Tip: You can use 'Local Mock Provider' above to test immediately with zero configuration!)"
                    )
                elif provider_key == "github":
                    err_msg = (
                        "GitHub credentials missing! Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET "
                        "to your prototypes/Oauth2.0/.env file, or export them in your shell."
                    )
                else:
                    err_msg = f"{config.name} credentials missing. Set environment variables."
                self._redirect(f"/?err={urllib.parse.quote(err_msg)}", session_id=session_id)
                return

            # Pure step 1: Generate PKCE & State
            pkce = generate_pkce_pair() if config.supports_pkce else None
            state = generate_secure_state()

            # Store in session
            session["oauth_state"] = state
            session["pkce"] = pkce
            session["provider"] = provider_key

            # Pure step 2: Build authorization URL
            auth_url = build_authorization_url(config, state, pkce)
            self._redirect(auth_url, session_id=session_id)

        # 3. OAuth Callback Handler
        elif path == "/callback":
            error_param = params.get("error")
            if error_param:
                error_desc = params.get("error_description", error_param)
                self._redirect(f"/?err={urllib.parse.quote('Authorization denied: ' + error_desc)}")
                return

            received_state = params.get("state", "")
            expected_state = session.get("oauth_state", "")

            # Pure step 3: CSRF State verification
            if not verify_state(expected_state, received_state):
                self._redirect("/?err=" + urllib.parse.quote("CSRF State verification failed! Possible attack."))
                return

            code = params.get("code")
            if not code:
                self._redirect("/?err=" + urllib.parse.quote("Missing authorization code in callback."))
                return

            provider_key = session.get("provider", "mock")
            config = get_provider_config(provider_key)
            pkce: Optional[PKCEPair] = session.get("pkce")
            code_verifier = pkce.code_verifier if pkce else None

            # Pure step 4: Exchange code for tokens
            token_result = exchange_code_for_token(config, code, code_verifier)
            if not token_result.is_success:
                self._redirect("/?err=" + urllib.parse.quote(token_result.error))
                return

            token: TokenResponse = token_result.value
            session["token"] = token

            # Pure step 5: Fetch user profile
            profile_result = fetch_user_profile(config, token)
            if profile_result.is_success:
                session["profile"] = profile_result.value

            self._redirect("/?msg=" + urllib.parse.quote("OAuth authentication successful!"), session_id=session_id)

        # 4. Mock OAuth Server: Authorize Consent Screen
        elif path == "/mock-oauth/authorize":
            client_id = params.get("client_id", "")
            redirect_uri = params.get("redirect_uri", "")
            scope = params.get("scope", "")
            state = params.get("state", "")
            code_challenge = params.get("code_challenge", "")
            code_challenge_method = params.get("code_challenge_method", "S256")

            consent_html = render_consent_page(
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=scope,
                state=state,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
            )
            self._send_html(consent_html)

        # 5. Mock OAuth Server: User Info Endpoint (Resource Server)
        elif path == "/mock-oauth/userinfo":
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                self._send_json({"error": "unauthorized", "error_description": "Bearer token required"}, 401)
                return

            access_token = auth_header[7:].strip()
            status, payload = mock_server_state.get_user_profile(access_token)
            self._send_json(payload, status)

        else:
            self.send_error(404, "Not Found")

    # ------------------------------------------------------------------------
    # POST Routes
    # ------------------------------------------------------------------------
    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        session_id, session = self._get_or_create_session()
        form_data = self._read_body_form()

        # 1. Mock Server: Consent approval
        if path == "/mock-oauth/approve":
            action = form_data.get("action")
            redirect_uri = form_data.get("redirect_uri", "")
            state = form_data.get("state", "")

            if action == "allow":
                code = mock_server_state.issue_auth_code(
                    client_id=form_data.get("client_id", ""),
                    redirect_uri=redirect_uri,
                    code_challenge=form_data.get("code_challenge") or None,
                    code_challenge_method=form_data.get("code_challenge_method") or None,
                    scope=form_data.get("scope", ""),
                )
                callback_url = f"{redirect_uri}?code={urllib.parse.quote(code)}&state={urllib.parse.quote(state)}"
                self._redirect(callback_url)
            else:
                callback_url = f"{redirect_uri}?error=access_denied&state={urllib.parse.quote(state)}"
                self._redirect(callback_url)

        # 2. Mock Server: Token endpoint
        elif path == "/mock-oauth/token":
            grant_type = form_data.get("grant_type")
            client_id = form_data.get("client_id", "")
            client_secret = form_data.get("client_secret")

            if grant_type == "authorization_code":
                status, payload = mock_server_state.exchange_code(
                    code=form_data.get("code", ""),
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=form_data.get("redirect_uri", ""),
                    code_verifier=form_data.get("code_verifier"),
                )
                self._send_json(payload, status)
            elif grant_type == "refresh_token":
                status, payload = mock_server_state.refresh(
                    refresh_token=form_data.get("refresh_token", ""),
                    client_id=client_id,
                )
                self._send_json(payload, status)
            else:
                self._send_json({"error": "unsupported_grant_type"}, 400)

        # 3. Client: Refresh Token action
        elif path == "/refresh":
            token: Optional[TokenResponse] = session.get("token")
            if not token or not token.refresh_token:
                self._redirect("/?err=" + urllib.parse.quote("No refresh token available."))
                return

            provider_key = session.get("provider", "mock")
            config = get_provider_config(provider_key)
            result = refresh_access_token(config, token.refresh_token)

            if result.is_success:
                session["token"] = result.value
                self._redirect("/?msg=" + urllib.parse.quote("Access token refreshed successfully!"))
            else:
                self._redirect("/?err=" + urllib.parse.quote(result.error))

        # 4. Client: Logout action
        elif path == "/logout":
            session.clear()
            self._redirect("/?msg=" + urllib.parse.quote("Logged out successfully."))

        else:
            self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: Any):
        """Clean terminal request logging."""
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.command} {self.path} - {args[0]}\n")


def run_server(port: int = PORT):
    """Starts the HTTP server."""
    server = HTTPServer(("0.0.0.0", port), FunctionalOAuthHandler)
    print("=" * 65)
    print(f"🚀 OAuth 2.0 Functional Prototype Server running at:")
    print(f"   👉 http://localhost:{port}")
    print("=" * 65)
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    run_server()

