"""Outbound network policy for vision-node addresses (S11, SSRF).

The brain fetches camera streams and snapshots from addresses that operators (eyes CRUD) or
nodes (telemetry) supply. Those addresses must point at a vision node on the private LAN,
never at the brain's own services, the Docker host, cloud metadata or the internet.

Rules:
- scheme: http, https or rtsp;
- host: an IPv4 literal inside RFC1918 (10/8, 172.16/12, 192.168/16), or a hostname listed
  exactly in ``SARI_ALLOWED_STREAM_HOSTS`` (comma separated, for LAN DNS names);
- always denied, even if allow-listed: loopback, link-local (169.254/16, metadata),
  ``localhost`` and ``host.docker.internal``. IPv6 literals are denied.
"""
import ipaddress
import os
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https", "rtsp"}
ALWAYS_DENIED_HOSTS = {"localhost", "host.docker.internal", "gateway.docker.internal", "metadata.google.internal"}
_PRIVATE_NETS = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


def _allowed_hostnames() -> set:
    raw = os.environ.get("SARI_ALLOWED_STREAM_HOSTS", "")
    return {h.strip().lower().rstrip(".") for h in raw.split(",") if h.strip()}


def validate_node_host(host: str) -> str:
    """Returns ``host`` if it is an allowed vision-node address, else raises ValueError."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError("node address is empty")
    name = host.strip().lower().rstrip(".")
    if name.startswith("[") and name.endswith("]"):
        raise ValueError("IPv6 node addresses are not allowed")
    if name in ALWAYS_DENIED_HOSTS:
        raise ValueError("node address points at the brain host")
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        if name in _allowed_hostnames():
            return host.strip()
        raise ValueError("hostname not allowed; use a private IPv4 address or add it to SARI_ALLOWED_STREAM_HOSTS")
    if ip.version != 4:
        raise ValueError("IPv6 node addresses are not allowed")
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        raise ValueError("node address is not a private LAN address")
    if not any(ip in net for net in _PRIVATE_NETS):
        raise ValueError("node address is not a private LAN address")
    return host.strip()


def validate_stream_url(url: str) -> str:
    """Returns ``url`` if it points at an allowed vision node, else raises ValueError."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("stream URL is empty")
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError on an invalid port
    except ValueError:
        raise ValueError("stream URL is malformed")
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("stream URL scheme must be http, https or rtsp")
    if not host:
        raise ValueError("stream URL has no host")
    if ":" in host:
        raise ValueError("IPv6 node addresses are not allowed")
    validate_node_host(host)
    return url.strip()


def is_allowed_stream_url(url: str) -> bool:
    try:
        validate_stream_url(url)
        return True
    except ValueError:
        return False
