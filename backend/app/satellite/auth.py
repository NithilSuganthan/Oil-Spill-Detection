"""Copernicus Data Space Ecosystem authentication.

Password-grant tokens against the CDSE Keycloak realm. Credentials are read
EXCLUSIVELY from environment/settings — never hardcoded, never logged.
Tokens are cached in memory and refreshed transparently; a refresh token is
preferred once issued so the password is used as rarely as possible.

Endpoint (official docs: documentation.dataspace.copernicus.eu/APIs/Token.html):
    POST https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token
"""

from __future__ import annotations

import logging
import threading
import time

import httpx

logger = logging.getLogger(__name__)

CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
    "/protocol/openid-connect/token"
)
CDSE_CLIENT_ID = "cdse-public"


class CopernicusAuthError(RuntimeError):
    """Raised when CDSE credentials are missing or the token request fails."""


class CdseTokenManager:
    """Thread-safe access-token cache for the Copernicus Data Space Ecosystem."""

    def __init__(
        self,
        username: str,
        password: str,
        token_url: str = CDSE_TOKEN_URL,
        client_id: str = CDSE_CLIENT_ID,
        http_client: httpx.Client | None = None,
    ) -> None:
        # Credentials may legitimately be absent while the app runs in
        # catalogue-only mode (STAC search is anonymous). get_token() raises
        # CopernicusAuthError the moment an authenticated call is attempted.
        self._username = username
        self._password = password
        self._token_url = token_url
        self._client_id = client_id
        self._client = http_client or httpx.Client(timeout=30.0)
        self._owns_client = http_client is None
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_token(self) -> str:
        with self._lock:
            if not self._username or not self._password:
                raise CopernicusAuthError(
                    "Copernicus download requires credentials. Set CDSE_USERNAME "
                    "and CDSE_PASSWORD in the environment (see .env.example). "
                    "Never hardcode them."
                )
            if self._access_token and time.monotonic() < self._expires_at - 60.0:
                return self._access_token
            self._fetch_token()
            return self._access_token  # type: ignore[return-value]

    def invalidate(self) -> None:
        with self._lock:
            self._access_token = None
            self._expires_at = 0.0

    # ------------------------------------------------------------------
    def _fetch_token(self) -> None:
        data: dict[str, str] = {
            "client_id": self._client_id,
            "grant_type": "password",
        }
        if self._refresh_token:
            # prefer refresh so the raw password is transmitted less often
            data.update(grant_type="refresh_token", refresh_token=self._refresh_token)
        else:
            data.update(username=self._username, password=self._password)

        try:
            resp = self._client.post(
                self._token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as exc:
            raise CopernicusAuthError(f"Token endpoint unreachable: {exc}") from exc

        if resp.status_code != 200:
            # never echo credentials or the response body (may contain hints)
            self._refresh_token = None
            raise CopernicusAuthError(
                f"CDSE token request failed with HTTP {resp.status_code}. "
                "Check CDSE_USERNAME / CDSE_PASSWORD (and 2FA requirements)."
            )

        payload = resp.json()
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token") or self._refresh_token
        self._expires_at = time.monotonic() + float(payload.get("expires_in", 300))
        logger.info("Obtained CDSE access token (expires in %ss)", payload.get("expires_in"))
