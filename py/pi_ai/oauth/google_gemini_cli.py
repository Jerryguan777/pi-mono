"""Gemini CLI OAuth flow (Google Cloud Code Assist).

Ported from packages/ai/src/utils/oauth/google-gemini-cli.ts.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from pi_ai.oauth.pkce import generate_pkce
from pi_ai.oauth.types import OAuthAuthInfo, OAuthCredentials, OAuthLoginCallbacks
from pi_ai.types import Model

_CLIENT_ID = base64.b64decode(
    "NjgxMjU1ODA5Mzk1LW9vOGZ0Mm9wcmRybnA5ZTNhcWY2YXYzaG1kaWIxMzVqLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t"
).decode()
_CLIENT_SECRET = base64.b64decode("R09DU1BYLTR1SGdNUG0tMW83U2stZ2VWNkN1NWNsWEZzeGw=").decode()
_REDIRECT_URI = "http://localhost:8085/oauth2callback"
_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"

_TIER_FREE = "free-tier"
_TIER_LEGACY = "legacy-tier"


def _parse_redirect_url(input_: str) -> dict[str, str | None]:
    value = input_.strip()
    if not value:
        return {}
    try:
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        return {
            "code": qs.get("code", [None])[0],
            "state": qs.get("state", [None])[0],
        }
    except Exception:
        return {}


def _get_default_tier(allowed_tiers: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not allowed_tiers:
        return {"id": _TIER_LEGACY}
    default = next((t for t in allowed_tiers if t.get("isDefault")), None)
    return default or {"id": _TIER_LEGACY}


def _is_vpc_sc_affected_user(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    details = error.get("details")
    if not isinstance(details, list):
        return False
    return any(d.get("reason") == "SECURITY_POLICY_VIOLATED" for d in details if isinstance(d, dict))


async def _poll_operation(
    operation_name: str,
    headers: dict[str, str],
    on_progress: Any = None,
) -> dict[str, Any]:
    attempt = 0
    async with httpx.AsyncClient() as client:
        while True:
            if attempt > 0:
                if on_progress:
                    on_progress(f"Waiting for project provisioning (attempt {attempt + 1})...")
                await asyncio.sleep(5)

            response = await client.get(
                f"{_CODE_ASSIST_ENDPOINT}/v1internal/{operation_name}",
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Failed to poll operation: {response.status_code} {response.reason_phrase}")

            data = response.json()
            if data.get("done"):
                return data  # type: ignore[no-any-return]

            attempt += 1


async def _discover_project(access_token: str, on_progress: Any = None) -> str:
    env_project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT_ID")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "google-api-nodejs-client/9.15.1",
        "X-Goog-Api-Client": "gl-node/22.17.0",
    }

    if on_progress:
        on_progress("Checking for existing Cloud Code Assist project...")

    async with httpx.AsyncClient() as client:
        load_response = await client.post(
            f"{_CODE_ASSIST_ENDPOINT}/v1internal:loadCodeAssist",
            headers=headers,
            json={
                "cloudaicompanionProject": env_project_id,
                "metadata": {
                    "ideType": "IDE_UNSPECIFIED",
                    "platform": "PLATFORM_UNSPECIFIED",
                    "pluginType": "GEMINI",
                    "duetProject": env_project_id,
                },
            },
        )

    if load_response.status_code != 200:
        try:
            error_payload = load_response.json()
        except Exception:
            error_payload = None

        if _is_vpc_sc_affected_user(error_payload):
            data: dict[str, Any] = {"currentTier": {"id": "standard-tier"}}
        else:
            raise RuntimeError(
                f"loadCodeAssist failed: {load_response.status_code} "
                f"{load_response.reason_phrase}: {load_response.text}"
            )
    else:
        data = load_response.json()

    if data.get("currentTier"):
        if data.get("cloudaicompanionProject"):
            return data["cloudaicompanionProject"]  # type: ignore[no-any-return]
        if env_project_id:
            return env_project_id
        raise RuntimeError(
            "This account requires setting GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_PROJECT_ID. "
            "See https://goo.gle/gemini-cli-auth-docs#workspace-gca"
        )

    tier = _get_default_tier(data.get("allowedTiers"))
    tier_id = tier.get("id", _TIER_FREE)

    if tier_id != _TIER_FREE and not env_project_id:
        raise RuntimeError(
            "This account requires setting GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_PROJECT_ID. "
            "See https://goo.gle/gemini-cli-auth-docs#workspace-gca"
        )

    if on_progress:
        on_progress("Provisioning Cloud Code Assist project (this may take a moment)...")

    onboard_body: dict[str, Any] = {
        "tierId": tier_id,
        "metadata": {
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
        },
    }

    if tier_id != _TIER_FREE and env_project_id:
        onboard_body["cloudaicompanionProject"] = env_project_id
        onboard_body["metadata"]["duetProject"] = env_project_id

    async with httpx.AsyncClient() as client:
        onboard_response = await client.post(
            f"{_CODE_ASSIST_ENDPOINT}/v1internal:onboardUser",
            headers=headers,
            json=onboard_body,
        )

    if onboard_response.status_code != 200:
        raise RuntimeError(
            f"onboardUser failed: {onboard_response.status_code} "
            f"{onboard_response.reason_phrase}: {onboard_response.text}"
        )

    lro_data = onboard_response.json()

    if not lro_data.get("done") and lro_data.get("name"):
        lro_data = await _poll_operation(lro_data["name"], headers, on_progress)

    project_id = lro_data.get("response", {}).get("cloudaicompanionProject", {}).get("id")
    if project_id:
        return project_id  # type: ignore[no-any-return]

    if env_project_id:
        return env_project_id

    raise RuntimeError(
        "Could not discover or provision a Google Cloud project. "
        "Try setting GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_PROJECT_ID. "
        "See https://goo.gle/gemini-cli-auth-docs#workspace-gca"
    )


async def _get_user_email(access_token: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if response.status_code == 200:
            return response.json().get("email")  # type: ignore[no-any-return]
    except Exception:
        pass
    return None


async def refresh_google_cloud_token(refresh_token: str, project_id: str) -> OAuthCredentials:
    """Refresh Google Cloud Code Assist token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise RuntimeError(f"Google Cloud token refresh failed: {response.text}")

    data = response.json()
    return OAuthCredentials(
        refresh=data.get("refresh_token", refresh_token),
        access=data["access_token"],
        expires=int(time.time() * 1000) + data["expires_in"] * 1000 - 5 * 60 * 1000,
        extra={"project_id": project_id},
    )


async def _start_callback_server() -> tuple[asyncio.AbstractServer, asyncio.Future[dict[str, str] | None]]:
    """Start a local HTTP server to receive the OAuth callback.

    Returns (server, future_with_code_and_state).
    """
    result_future: asyncio.Future[dict[str, str] | None] = asyncio.get_event_loop().create_future()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            request_str = request_line.decode("utf-8", errors="replace")

            # Parse the GET request
            parts = request_str.split(" ")
            if len(parts) < 2:
                writer.close()
                return

            path = parts[1]
            parsed = urlparse(path)

            if parsed.path == "/oauth2callback":
                qs = parse_qs(parsed.query)
                code = qs.get("code", [None])[0]
                state = qs.get("state", [None])[0]
                error = qs.get("error", [None])[0]

                if error:
                    body = f"<html><body><h1>Authentication Failed</h1><p>Error: {error}</p></body></html>"
                    response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n{body}"
                    writer.write(response.encode())
                elif code and state:
                    body = (
                        "<html><body><h1>Authentication Successful</h1><p>You can close this window.</p></body></html>"
                    )
                    response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n{body}"
                    writer.write(response.encode())
                    if not result_future.done():
                        result_future.set_result({"code": code, "state": state})
                else:
                    body = "<html><body><h1>Authentication Failed</h1><p>Missing parameters.</p></body></html>"
                    response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n{body}"
                    writer.write(response.encode())
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")

            await writer.drain()
            writer.close()
        except Exception:
            with contextlib.suppress(Exception):
                writer.close()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 8085)
    return server, result_future


async def login_gemini_cli(
    on_auth: Any,
    on_progress: Any = None,
    on_manual_code_input: Any = None,
) -> OAuthCredentials:
    """Login with Gemini CLI (Google Cloud Code Assist) OAuth."""
    verifier, challenge = await generate_pkce()

    if on_progress:
        on_progress("Starting local server for OAuth callback...")

    server, code_future = await _start_callback_server()

    try:
        params = {
            "client_id": _CLIENT_ID,
            "response_type": "code",
            "redirect_uri": _REDIRECT_URI,
            "scope": " ".join(_SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": verifier,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        auth_url = f"{_AUTH_URL}?{query}"

        on_auth(OAuthAuthInfo(url=auth_url, instructions="Complete the sign-in in your browser."))

        if on_progress:
            on_progress("Waiting for OAuth callback...")

        code: str | None = None

        if on_manual_code_input:
            # Race between browser callback and manual input
            manual_task = asyncio.create_task(on_manual_code_input())
            try:
                done, pending = await asyncio.wait(
                    [code_future, manual_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()

                for task in done:
                    result = task.result()
                    if isinstance(result, dict) and "code" in result:
                        if result.get("state") != verifier:
                            raise RuntimeError("OAuth state mismatch - possible CSRF attack")
                        code = result["code"]
                    elif isinstance(result, str):
                        parsed = _parse_redirect_url(result)
                        if parsed.get("state") and parsed["state"] != verifier:
                            raise RuntimeError("OAuth state mismatch - possible CSRF attack")
                        code = parsed.get("code")
            except asyncio.CancelledError:
                pass
        else:
            result = await code_future
            if result and result.get("code"):
                if result.get("state") != verifier:
                    raise RuntimeError("OAuth state mismatch - possible CSRF attack")
                code = result["code"]

        if not code:
            raise RuntimeError("No authorization code received")

        if on_progress:
            on_progress("Exchanging authorization code for tokens...")

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                _TOKEN_URL,
                data={
                    "client_id": _CLIENT_ID,
                    "client_secret": _CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": _REDIRECT_URI,
                    "code_verifier": verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if token_response.status_code != 200:
            raise RuntimeError(f"Token exchange failed: {token_response.text}")

        token_data = token_response.json()
        if not token_data.get("refresh_token"):
            raise RuntimeError("No refresh token received. Please try again.")

        if on_progress:
            on_progress("Getting user info...")
        email = await _get_user_email(token_data["access_token"])

        project_id = await _discover_project(token_data["access_token"], on_progress)

        expires_at = int(time.time() * 1000) + token_data["expires_in"] * 1000 - 5 * 60 * 1000

        return OAuthCredentials(
            refresh=token_data["refresh_token"],
            access=token_data["access_token"],
            expires=expires_at,
            extra={"project_id": project_id, "email": email},
        )
    finally:
        server.close()
        await server.wait_closed()


class GeminiCliOAuthProvider:
    """Google Cloud Code Assist (Gemini CLI) OAuth provider."""

    @property
    def id(self) -> str:
        return "google-gemini-cli"

    @property
    def name(self) -> str:
        return "Google Cloud Code Assist (Gemini CLI)"

    @property
    def uses_callback_server(self) -> bool:
        return True

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredentials:
        return await login_gemini_cli(callbacks.on_auth, callbacks.on_progress, callbacks.on_manual_code_input)

    async def refresh_token(self, credentials: OAuthCredentials) -> OAuthCredentials:
        project_id = credentials.extra.get("project_id")
        if not project_id:
            raise RuntimeError("Google Cloud credentials missing project_id")
        return await refresh_google_cloud_token(credentials.refresh, project_id)

    def get_api_key(self, credentials: OAuthCredentials) -> str:
        project_id = credentials.extra.get("project_id", "")
        return json.dumps({"token": credentials.access, "projectId": project_id})

    def modify_models(self, models: list[Model], credentials: OAuthCredentials) -> list[Model]:
        return models


gemini_cli_oauth_provider = GeminiCliOAuthProvider()
