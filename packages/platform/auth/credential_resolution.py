"""Credential extraction from HTTP requests (bearer token, session cookie, remote addr)."""
from __future__ import annotations

from fastapi import Request


def request_remote_addr(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    if request.client is None:
        return None
    return request.client.host


def cookie_secure_for_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme.lower() == "https"


def bearer_token_from_request(request: Request) -> str | None:
    header_value = request.headers.get("authorization", "").strip()
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
