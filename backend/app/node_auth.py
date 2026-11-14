"""Per-node credentials for machine-to-machine endpoints (vision nodes -> brain).

SARI_NODE_KEYS="Jetson-PTZ_1:<key>,Jetson-PTZ_2:<key>". With no keys configured every node request is rejected.
"""
import hmac
import os
from typing import Dict, Optional

from fastapi import Header, HTTPException

NODE_KEY_HEADER = "X-SARI-Node-Key"


def parse_node_keys(raw: str) -> Dict[str, str]:
    """Return {key: node_id}. Raises ValueError on malformed entries or a key shared by two nodes."""
    keys: Dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        node_id, sep, key = entry.partition(":")
        node_id, key = node_id.strip(), key.strip()
        if not sep or not node_id or not key:
            raise ValueError("SARI_NODE_KEYS entries must look like <node_id>:<key>")
        if key in keys:
            raise ValueError("Each node needs its own key in SARI_NODE_KEYS")
        keys[key] = node_id
    return keys


def node_for_key(supplied: Optional[str]) -> Optional[str]:
    if not supplied:
        return None
    for key, node_id in parse_node_keys(os.environ.get("SARI_NODE_KEYS", "")).items():
        if hmac.compare_digest(supplied.encode(), key.encode()):
            return node_id
    return None


def require_node(x_sari_node_key: Optional[str] = Header(default=None, alias=NODE_KEY_HEADER)) -> str:
    """FastAPI dependency: returns the authenticated node id or raises 401."""
    node_id = node_for_key(x_sari_node_key)
    if not node_id:
        raise HTTPException(status_code=401, detail="Invalid or missing node credentials")
    return node_id
