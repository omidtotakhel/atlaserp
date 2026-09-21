# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Process-wide registry of adapter classes keyed by provider_code.

Concrete adapters (Mirsal 2, FASAH, DCSA, Aramex, etc.) call
``register('mirsal2', Mirsal2Adapter)`` at module import time. The
profile and message models look up classes by code via ``get`` to
dispatch health checks, sends, and replays.

Two reasons for a process-level registry rather than ir.actions or a
database table: adapter classes are Python implementation, not
configurable data; and lookup happens on the hot path of every
adapter call, so a dict beats an ORM read.

Tests exercise this registry by registering a TestAdapter and asserting
the dispatch hits the registered class. The registry is reset between
tests via the ``adapter_registry_isolation`` fixture in
``tests/common.py``.
"""
from __future__ import annotations

from typing import Optional, Type

_REGISTRY: dict = {}


def register(provider_code: str, adapter_cls: Type) -> None:
    """Register an adapter class for a provider code.

    Re-registering the same code with a different class is allowed and
    overwrites silently; this lets country localisation modules
    swap a default implementation with a country-specific subclass.
    """
    if not provider_code:
        raise ValueError("provider_code must be non-empty")
    _REGISTRY[provider_code] = adapter_cls


def get(provider_code: str) -> Optional[Type]:
    """Look up the adapter class for a provider code, or None if absent."""
    return _REGISTRY.get(provider_code)


def keys() -> list:
    """Return all registered provider codes for diagnostics."""
    return list(_REGISTRY.keys())


def clear() -> None:
    """Test-only: clear the registry. Production code should never call this."""
    _REGISTRY.clear()
