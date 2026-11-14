"""Compatibility alias: the alert pipeline lives in `app.application.alert_ingest`.

The module replaces itself in `sys.modules`, so `app.services.alert_ingest` *is* the application
module: imports and `monkeypatch.setattr(alert_ingest, ...)` keep hitting the names the pipeline uses.
"""
import sys

from ..application import alert_ingest as _impl

sys.modules[__name__] = _impl
