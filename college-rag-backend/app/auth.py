"""Authentication & anonymous client identification.

* Public endpoints are anonymous. History is scoped per client via ``X-Client-Id``; when
  absent, a deterministic hash of (client IP, User-Agent, secret salt) is used so raw IPs
  are never stored or logged.
* Admin endpoints are protected by ``ADMIN_API_KEY`` (``X-Admin-Api-Key`` or
  ``Authorization: Bearer``) when ``ADMIN_AUTH_MODE=api_key``, or by Microsoft Entra ID
  JWT role validation when ``ADMIN_AUTH_MODE=entra``. Swap by changing two env vars.
"""
from __future__ import annotations

import hmac
import json
import re
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request

from app.config import Settings
from app.core.text import sha256

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-:.]{1,128}$")
_jwks_cache: dict[str, dict[str, Any]] = {}


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def resolve_client_id(request: Request, settings: Settings = Depends(get_settings_dep)) -> str:
    raw = (request.headers.get("X-Client-Id") or "").strip()
    if raw and _CLIENT_ID_RE.match(raw):
        return f"cid:{sha256(raw)[:32]}"
    # Derive an anonymous id from IP + User-Agent + server salt (no PII stored).
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = xff or (request.client.host if request.client else "unknown")
    ua = request.headers.get("User-Agent", "")
    salt = settings.client_id_salt.get_secret_value()
    return f"anon:{sha256(f'{salt}|{ip}|{ua}')[:32]}"


def _extract_token(request: Request) -> str:
    hdr = request.headers.get("X-Admin-Api-Key") or request.headers.get("ADMIN_API_KEY") or ""
    if hdr:
        return hdr.strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


async def _verify_entra_jwt(token: str, s: Settings) -> dict[str, Any]:  # pragma: no cover - requires Entra JWKS
    import jwt
    from jwt.algorithms import RSAAlgorithm

    if not (s.entra_tenant_id and s.entra_audience):
        raise HTTPException(status_code=503, detail="Admin authentication is not configured.")
    jwks_url = f"https://login.microsoftonline.com/{s.entra_tenant_id}/discovery/v2.0/keys"
    if jwks_url not in _jwks_cache:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(jwks_url)
            r.raise_for_status()
            _jwks_cache[jwks_url] = r.json()
    header = jwt.get_unverified_header(token)
    key = next((k for k in _jwks_cache[jwks_url].get("keys", []) if k.get("kid") == header.get("kid")), None)
    if not key:
        raise HTTPException(status_code=401, detail="Invalid token.")
    pub: Any = RSAAlgorithm.from_jwk(json.dumps(key))
    issuers = [
        f"https://login.microsoftonline.com/{s.entra_tenant_id}/v2.0",
        f"https://sts.windows.net/{s.entra_tenant_id}/",
    ]
    claims: dict[str, Any] = jwt.decode(token, pub, algorithms=["RS256"], audience=s.entra_audience, issuer=issuers)
    roles = claims.get("roles") or []
    if s.entra_admin_role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient role.")
    return claims


async def require_admin(request: Request, settings: Settings = Depends(get_settings_dep)) -> str:
    token = _extract_token(request)
    if settings.admin_auth_mode == "entra":
        if not token:
            raise HTTPException(status_code=401, detail="Missing bearer token.")
        claims = await _verify_entra_jwt(token, settings)
        return str(claims.get("oid") or claims.get("sub") or "entra-admin")

    expected = settings.admin_api_key.get_secret_value()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin API key is not configured.")
    if not token or not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return "api-key-admin"

