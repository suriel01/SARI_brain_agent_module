"""Who may run which physical tool."""
from dataclasses import dataclass, field

from .actions import ACTIVATE_SIREN, ALL_TOOLS


def has_permission(user: dict, flag: str) -> bool:
    """An admin holds every permission; anyone else needs the flag set on their user record."""
    return user.get("role") == "admin" or bool(user.get(flag))


@dataclass(frozen=True)
class Actor:
    """Who is asking for a physical action, and through which channel."""

    name: str
    channel: str
    can_control_hardware: bool
    allowed_tools: frozenset = field(default=frozenset(ALL_TOOLS))

    @classmethod
    def from_user(cls, user: dict, channel: str) -> "Actor":
        return cls(
            name=str(user.get("username") or user.get("sub") or "unknown"),
            channel=channel,
            can_control_hardware=has_permission(user, "can_control_hardware"),
        )

    @classmethod
    def node(cls, node_id: str) -> "Actor":
        """An authenticated vision node may raise the alarm, never silence it or touch gates."""
        return cls(name=f"node:{node_id}", channel="node", can_control_hardware=True, allowed_tools=frozenset(ACTIVATE_SIREN))

    def may_run(self, tool_name: str) -> bool:
        return self.can_control_hardware and tool_name in self.allowed_tools
