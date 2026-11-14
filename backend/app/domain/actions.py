"""Physical tool names: Spanish/English aliases and their canonical audit names."""

ACTIVATE_SIREN = frozenset({"activate_siren", "activar_sirena"})
DEACTIVATE_SIREN = frozenset({"deactivate_siren", "desactivar_sirena"})
LOCK_GATES = frozenset({"lock_gates", "cerrar_accesos"})
UNLOCK_GATES = frozenset({"unlock_gates", "abrir_accesos"})
ALL_TOOLS = ACTIVATE_SIREN | DEACTIVATE_SIREN | LOCK_GATES | UNLOCK_GATES

DEFAULT_SIREN_SECONDS = 30


def canonical_action(tool_name: str) -> str:
    """Maps Spanish/English tool aliases to one canonical name for the audit trail."""
    for canonical, aliases in (
        ("activate_siren", ACTIVATE_SIREN),
        ("deactivate_siren", DEACTIVATE_SIREN),
        ("lock_gates", LOCK_GATES),
        ("unlock_gates", UNLOCK_GATES),
    ):
        if tool_name in aliases:
            return canonical
    return str(tool_name)[:50]


def siren_duration(args: dict):
    """Requested siren duration: `duration_seconds`, else `duracion_segundos`, else the default."""
    return args.get("duration_seconds") or args.get("duracion_segundos", DEFAULT_SIREN_SECONDS)
