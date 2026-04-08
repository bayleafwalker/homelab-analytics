"""Credential extraction from HTTP requests (bearer token, session cookie, remote addr)."""
from __future__ import annotations

from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

from fastapi import Request


def _trusted_forwarder_networks_for_request(
    request: Request,
) -> tuple[IPv4Network | IPv6Network, ...]:
    state = getattr(getattr(request, "app", None), "state", None)
    if state is None:
        return ()
    networks = getattr(state, "trusted_forwarder_networks", ())
    if not networks:
        cidrs = getattr(state, "trusted_forwarder_cidrs", ())
        if not cidrs:
            return ()
        return tuple(ip_network(cidr, strict=False) for cidr in cidrs if cidr.strip())
    return tuple(networks)


def _request_comes_from_trusted_forwarder(request: Request) -> bool:
    trusted_forwarder_networks = _trusted_forwarder_networks_for_request(request)
    if not trusted_forwarder_networks or request.client is None:
        return False
    try:
        peer_address = ip_address(request.client.host)
    except ValueError:
        return False
    return any(peer_address in network for network in trusted_forwarder_networks)


def _first_header_value(header_value: str) -> str | None:
    candidate = header_value.split(",", 1)[0].strip()
    return candidate or None


def request_remote_addr(request: Request) -> str | None:
    if _request_comes_from_trusted_forwarder(request):
        forwarded_for = _first_header_value(request.headers.get("x-forwarded-for", ""))
        if forwarded_for:
            return forwarded_for
    if request.client is None:
        return None
    return request.client.host


def cookie_secure_for_request(request: Request) -> bool:
    if _request_comes_from_trusted_forwarder(request):
        forwarded_proto = _first_header_value(request.headers.get("x-forwarded-proto", ""))
        if forwarded_proto:
            return forwarded_proto.lower() == "https"
    return request.url.scheme.lower() == "https"


def bearer_token_from_request(request: Request) -> str | None:
    header_value = request.headers.get("authorization", "").strip()
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
