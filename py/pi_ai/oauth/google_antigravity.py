"""Antigravity OAuth flow (Gemini 3, Claude, GPT-OSS via Google Cloud).

Ported from packages/ai/src/utils/oauth/google-antigravity.ts.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from pi_ai.oauth.pkce import generate_pkce
from pi_ai.oauth.types import OAuthAuthInfo, OAuthCredentials, OAuthLoginCallbacks
from pi_ai.types import Model

_CLIENT_ID = base64.b64decode(
    "MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ=="
).decode()
_CLIENT_SECRET = base64.b64decode("R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6NnFEQWY=").decode()
_REDIRECT_URI = "http://localhost:51121/oauth-callback"
_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_DEFAULT_PROJECT_ID = "rising-fact-p41fc"


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


async def _discover_project(access_token: str, on_progress: Any = None) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "google-api-nodejs-client/9.15.1",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": json.dumps(
            {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        ),
    }

    endpoints = [
        "https://cloudcode-pa.googleapis.com",
        "https://daily-cloudcode-pa.sandbox.googleapis.com",
    ]

    if on_progress:
        on_progress("Checking for existing project...")

    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            try:
                response = await client.post(
                    f"{endpoint}/v1internal:loadCodeAssist",
                    headers=headers,
                    json={
                        "metadata": {
                            "ideType": "IDE_UNSPECIFIED",
                            "platform": "PLATFORM_UNSPECIFIED",
                            "pluginType": "GEMINI",
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    project = data.get("cloudaicompanionProject")
                    if isinstance(project, str) and project:
                        return project
                    if isinstance(project, dict) and project.get("id"):
                        return project["id"]  # type: ignore[no-any-return]
            except Exception:
                continue

    if on_progress:
        on_progress("Using default project...")
    return _DEFAULT_PROJECT_ID


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


async def refresh_antigravity_token(refresh_token: str, project_id: str) -> OAuthCredentials:
    """Refresh Antigravity token."""
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
        raise RuntimeError(f"Antigravity token refresh failed: {response.text}")

    data = response.json()
    return OAuthCredentials(
        refresh=data.get("refresh_token", refresh_token),
        access=data["access_token"],
        expires=int(time.time() * 1000) + data["expires_in"] * 1000 - 5 * 60 * 1000,
        extra={"project_id": project_id},
    )


async def _start_callback_server() -> tuple[asyncio.AbstractServer, asyncio.Future[dict[str, str] | None]]:
    """Start a local HTTP server for the Antigravity OAuth callback."""
    result_future: asyncio.Future[dict[str, str] | None] = asyncio.get_event_loop().create_future()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            request_str = request_line.decode("utf-8", errors="replace")
            parts = request_str.split(" ")
            if len(parts) < 2:
                writer.close()
                return

            path = parts[1]
            parsed = urlparse(path)

            if parsed.path == "/oauth-callback":
                qs = parse_qs(parsed.query)
                code = qs.get("code", [None])[0]
                state = qs.get("state", [None])[0]
                error = qs.get("error", [None])[0]

                if error:
                    body = f"<html><body><h1>Authentication Failed</h1><p>Error: {error}</p></body></html>"
                    writer.write(f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n{body}".encode())
                elif code and state:
                    body = (
                        "<html><body><h1>Authentication Successful</h1><p>You can close this window.</p></body></html>"
                    )
                    writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n{body}".encode())
                    if not result_future.done():
                        result_future.set_result({"code": code, "state": state})
                else:
                    body = "<html><body><h1>Authentication Failed</h1><p>Missing parameters.</p></body></html>"
                    writer.write(f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n{body}".encode())
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")

            await writer.drain()
            writer.close()
        except Exception:
            with contextlib.suppress(Exception):
                writer.close()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 51121)
    return server, result_future


async def login_antigravity(
    on_auth: Any,
    on_progress: Any = None,
    on_manual_code_input: Any = None,
) -> OAuthCredentials:
    """Login with Antigravity OAuth."""
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


class AntigravityOAuthProvider:
    """Antigravity OAuth provider (Gemini 3, Claude, GPT-OSS)."""

    @property
    def id(self) -> str:
        return "google-antigravity"

    @property
    def name(self) -> str:
        return "Antigravity (Gemini 3, Claude, GPT-OSS)"

    @property
    def uses_callback_server(self) -> bool:
        return True

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredentials:
        return await login_antigravity(callbacks.on_auth, callbacks.on_progress, callbacks.on_manual_code_input)

    async def refresh_token(self, credentials: OAuthCredentials) -> OAuthCredentials:
        project_id = credentials.extra.get("project_id")
        if not project_id:
            raise RuntimeError("Antigravity credentials missing project_id")
        return await refresh_antigravity_token(credentials.refresh, project_id)

    def get_api_key(self, credentials: OAuthCredentials) -> str:
        project_id = credentials.extra.get("project_id", "")
        return json.dumps({"token": credentials.access, "projectId": project_id})

    def modify_models(self, models: list[Model], credentials: OAuthCredentials) -> list[Model]:
        return models


antigravity_oauth_provider = AntigravityOAuthProvider()
