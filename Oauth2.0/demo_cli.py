"""Interactive CLI Walkthrough of the OAuth 2.0 Functional Pipeline.

Demonstrates pure function composition, PKCE generation, CSRF state verification,
and token transformations entirely in terminal.
"""

from __future__ import annotations
import json
from config import create_mock_config
from oauth_core import (
    compute_code_challenge,
    generate_pkce_pair,
    generate_secure_state,
    build_authorization_url,
    build_token_request_body,
    parse_token_response,
    parse_user_profile,
    pipe,
    verify_state,
)


def header(title: str):
    print("\n" + "=" * 60)
    print(f"🔹 {title}")
    print("=" * 60)


def run_cli_demo():
    header("STEP 1: Functional PKCE Generation (RFC 7636)")
    pkce = generate_pkce_pair()
    print(f"Code Verifier (Entropy):   {pkce.code_verifier}")
    print(f"Code Challenge (SHA-256):  {pkce.code_challenge}")
    print(f"Challenge Method:          {pkce.code_challenge_method}")

    # Verify mathematical purity
    manual_challenge = compute_code_challenge(pkce.code_verifier)
    assert manual_challenge == pkce.code_challenge
    print("✓ Cryptographic assertion passed: compute_code_challenge(verifier) == challenge")

    header("STEP 2: Generate Secure CSRF State & Auth URL")
    config = create_mock_config()
    state = generate_secure_state()
    auth_url = build_authorization_url(config, state, pkce)
    print(f"State Parameter (Anti-CSRF): {state}")
    print(f"Constructed Authorization URL:\n  {auth_url}")

    header("STEP 3: Validate Callback State (Timing-Safe Comparison)")
    tampered_state = state[:-1] + ("A" if state[-1] != "A" else "B")
    print(f"Original state matches itself:  {verify_state(state, state)} (Valid)")
    print(f"Tampered state rejected:       {not verify_state(state, tampered_state)} (Blocked)")

    header("STEP 4: Prepare Token Exchange Request Body (Pure Transformation)")
    simulated_code = "authcode_demo_9876543210"
    payload = build_token_request_body(config, simulated_code, pkce.code_verifier)
    print("Form POST Payload prepared:")
    for k, v in payload.items():
        print(f"  {k:15}: {v}")

    header("STEP 5: Functional Parsing of Provider Token Response")
    raw_provider_response = {
        "access_token": "at_demo_4f9812ac6b99e710d2",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "rt_demo_e710d24f9812ac6b99",
        "scope": "read:profile read:email",
    }
    token_result = parse_token_response(raw_provider_response)
    if token_result.is_success:
        token = token_result.value
        print(f"Access Token:  {token.access_token}")
        print(f"Token Type:    {token.token_type}")
        print(f"Expires In:    {token.expires_in}s")
        print(f"Refresh Token: {token.refresh_token}")

    header("STEP 6: Normalizing User Claims with Functional Normalizer")
    raw_user_claims = {
        "id": "usr_ada_001",
        "name": "Ada Lovelace",
        "email": "ada@analytical-engine.io",
        "role": "Chief Mathematician",
    }
    profile = parse_user_profile(raw_user_claims, provider_name="Mock Provider")
    print(f"Profile ID:       {profile.id}")
    print(f"Profile Name:     {profile.name}")
    print(f"Profile Email:    {profile.email}")
    print(f"Provider:         {profile.provider}")

    header("STEP 7: Functional Composition with pipe()")
    # Demonstrating pipe(data, f1, f2, f3)
    def extract_token(resp: dict) -> str:
        return resp.get("access_token", "")

    def mask_secret(secret: str) -> str:
        return secret[:6] + "..." + secret[-4:] if len(secret) > 10 else secret

    masked = pipe(
        raw_provider_response,
        extract_token,
        mask_secret,
    )
    print(f"Pipelined transformation: {raw_provider_response['access_token']} -> {masked}")
    print("\n✅ All functional OAuth 2.0 pipeline steps completed successfully!")


if __name__ == "__main__":
    run_cli_demo()

