"""Comprehensive Unit Tests for OAuth 2.0 Functional Implementation.

Covers RFC 7636 PKCE test vectors, state verification, pure transformations,
and Result monad error handling.
"""

from __future__ import annotations
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OAuthConfig, create_mock_config
from oauth_core import (
    Failure,
    PKCEPair,
    Success,
    build_authorization_url,
    build_refresh_token_request_body,
    build_token_request_body,
    compute_code_challenge,
    generate_pkce_pair,
    generate_secure_state,
    parse_token_response,
    parse_user_profile,
    pipe,
    verify_state,
)


class TestOAuthFunctionalCore(unittest.TestCase):

    def test_pkce_rfc7636_official_test_vector(self):
        """Validates against the official RFC 7636 Appendix B test vector."""
        rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        actual_challenge = compute_code_challenge(rfc_verifier)
        self.assertEqual(actual_challenge, expected_challenge)

    def test_generate_pkce_pair(self):
        """Verifies random PKCE pair generation meets RFC requirements."""
        pkce = generate_pkce_pair()
        self.assertGreaterEqual(len(pkce.code_verifier), 43)
        self.assertLessEqual(len(pkce.code_verifier), 128)
        self.assertEqual(pkce.code_challenge_method, "S256")
        self.assertEqual(compute_code_challenge(pkce.code_verifier), pkce.code_challenge)

    def test_state_generation_and_verification(self):
        """Verifies CSRF state generation and constant-time validation."""
        state1 = generate_secure_state()
        state2 = generate_secure_state()
        self.assertNotEqual(state1, state2)
        self.assertTrue(verify_state(state1, state1))
        self.assertFalse(verify_state(state1, state2))
        self.assertFalse(verify_state(state1, state1 + "tampered"))
        self.assertFalse(verify_state("", state1))

    def test_build_authorization_url_with_pkce(self):
        """Verifies query parameters for PKCE authorization URL."""
        config = create_mock_config("http://localhost:8000")
        state = "xyz123state"
        pkce = PKCEPair("my_verifier", "my_challenge", "S256")

        url = build_authorization_url(config, state, pkce)
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=mock-client-id-12345", url)
        self.assertIn("state=xyz123state", url)
        self.assertIn("code_challenge=my_challenge", url)
        self.assertIn("code_challenge_method=S256", url)

    def test_build_authorization_url_without_pkce(self):
        """Verifies URL when provider does not support or use PKCE."""
        config = OAuthConfig(
            name="Non-PKCE Provider",
            client_id="cid",
            client_secret="sec",
            authorize_endpoint="https://example.com/auth",
            token_endpoint="https://example.com/token",
            userinfo_endpoint="https://example.com/user",
            redirect_uri="https://app.com/cb",
            scopes=("scope1",),
            supports_pkce=False,
        )
        url = build_authorization_url(config, "test_state", PKCEPair("v", "c", "S256"))
        self.assertNotIn("code_challenge", url)

    def test_build_token_request_body(self):
        """Verifies form body construction for code exchange."""
        config = create_mock_config()
        body = build_token_request_body(config, "code_abc", "verifier_xyz")
        self.assertEqual(body["grant_type"], "authorization_code")
        self.assertEqual(body["client_id"], config.client_id)
        self.assertEqual(body["code"], "code_abc")
        self.assertEqual(body["code_verifier"], "verifier_xyz")
        self.assertEqual(body["client_secret"], config.client_secret)

    def test_build_refresh_token_request_body(self):
        """Verifies form body construction for token refresh."""
        config = create_mock_config()
        body = build_refresh_token_request_body(config, "refresh_123")
        self.assertEqual(body["grant_type"], "refresh_token")
        self.assertEqual(body["refresh_token"], "refresh_123")
        self.assertEqual(body["client_id"], config.client_id)

    def test_parse_token_response_success(self):
        """Verifies parsing of standard successful token response."""
        raw = {
            "access_token": "token_abc",
            "token_type": "Bearer",
            "expires_in": "3600",
            "refresh_token": "refresh_xyz",
            "scope": "read write",
        }
        res = parse_token_response(raw)
        self.assertTrue(res.is_success)
        self.assertEqual(res.value.access_token, "token_abc")
        self.assertEqual(res.value.expires_in, 3600)
        self.assertEqual(res.value.refresh_token, "refresh_xyz")

    def test_parse_token_response_failure(self):
        """Verifies parsing of provider error responses."""
        raw = {"error": "invalid_grant", "error_description": "Code expired"}
        res = parse_token_response(raw)
        self.assertFalse(res.is_success)
        self.assertIn("Code expired", res.error)

    def test_parse_user_profile_normalization(self):
        """Verifies normalizing different provider schemas."""
        github_data = {"id": 100, "login": "octocat", "email": "octo@github.com", "avatar_url": "https://gh.com/pic"}
        profile_gh = parse_user_profile(github_data, "GitHub")
        self.assertEqual(profile_gh.id, "100")
        self.assertEqual(profile_gh.name, "octocat")
        self.assertEqual(profile_gh.email, "octo@github.com")

        google_data = {"sub": "google-999", "name": "Google User", "email": "user@gmail.com", "picture": "https://gg.com/pic"}
        profile_gg = parse_user_profile(google_data, "Google")
        self.assertEqual(profile_gg.id, "google-999")
        self.assertEqual(profile_gg.name, "Google User")

    def test_result_monad_map_and_bind(self):
        """Verifies functional Result monad map and bind operations."""
        s = Success(10)
        mapped = s.map(lambda x: x * 2)
        self.assertEqual(mapped.value, 20)

        bound = s.bind(lambda x: Success(f"val: {x}"))
        self.assertEqual(bound.value, "val: 10")

        f = Failure("original error")
        self.assertIs(f.map(lambda x: x * 2), f)
        self.assertIs(f.bind(lambda x: Success(x)), f)

    def test_functional_pipeline(self):
        """Verifies pure function composition with pipe()."""
        result = pipe(
            5,
            lambda x: x + 10,  # 15
            lambda x: x * 2,   # 30
            str,               # "30"
        )
        self.assertEqual(result, "30")


if __name__ == "__main__":
    unittest.main()

