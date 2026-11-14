"""Deprecated `HardwareState` facade over the configured StateRepository.

Application code uses `app.adapters.composition.state` directly. This facade only keeps the old
class-attribute API (``HardwareState.siren_active = True``, ``HardwareState.nodes[...]``) working for
tests and scripts written against the in-memory class. Every read goes to the repository and every
write goes through it, so the facade never holds state of its own.
"""
from typing import Any, Dict, List, Optional

from ...domain.state import RUNTIME_FIELDS


def _repo():
    from .. import composition

    return composition.state


class _NodeView(dict):
    """Snapshot of one node; item writes are merged into the repository."""

    def __init__(self, node_id: str, data: Dict[str, Any]):
        super().__init__(data)
        self._node_id = node_id

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        _repo().merge_node(self._node_id, {key: value})

    def update(self, *args, **kwargs):
        fields = dict(*args, **kwargs)
        super().update(fields)
        _repo().merge_node(self._node_id, fields)


class _NodesView(dict):
    """Snapshot of all nodes; writes, removals and clears go to the repository."""

    def __init__(self):
        super().__init__({node_id: _NodeView(node_id, data) for node_id, data in _repo().list_nodes().items()})

    def __setitem__(self, node_id, data):
        super().__setitem__(node_id, _NodeView(node_id, data))
        _repo().put_node(node_id, dict(data))

    def __delitem__(self, node_id):
        super().__delitem__(node_id)
        _repo().remove_node(node_id)

    def pop(self, node_id, *default):
        value = super().pop(node_id, *default)
        _repo().remove_node(node_id)
        return value

    def clear(self):
        super().clear()
        _repo().clear_nodes()


class _HardwareStateMeta(type):
    def __getattr__(cls, name):
        if name in RUNTIME_FIELDS:
            return getattr(_repo().snapshot(), name)
        raise AttributeError(name)

    def __setattr__(cls, name, value):
        if name in RUNTIME_FIELDS:
            _repo().overwrite_runtime(**{name: value})
        else:
            super().__setattr__(name, value)

    @property
    def nodes(cls) -> Dict[str, Dict[str, Any]]:
        return _NodesView()

    @property
    def logs(cls) -> List[Dict[str, Any]]:
        return _repo().list_logs()


class HardwareState(metaclass=_HardwareStateMeta):
    """Deprecated: use `app.adapters.composition.state` (a StateRepository)."""

    @classmethod
    def add_log(cls, msg: str, level: str = "INFO", camera_module: str = "SYS_CORE") -> None:
        _repo().add_log(msg, level=level, camera_module=camera_module)

    @classmethod
    def record_node_activity(cls, node_id: str, ip: Optional[str] = None) -> None:
        _repo().record_node_activity(node_id, ip=ip)

    @classmethod
    def purge_expired_logs(cls) -> None:
        _repo().purge_expired_logs()
