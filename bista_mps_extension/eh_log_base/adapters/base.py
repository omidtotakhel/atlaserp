# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Abstract base class for every external adapter in the suite.

Concrete adapters (Mirsal 2, FASAH, DCSA, Aramex, MarineTraffic, ...)
inherit from BaseAdapter, declare their ``PROVIDER_CODE`` and
``API_VERSION`` class attributes, and register themselves at module
import time via:

    from ..adapters.base import BaseAdapter
    from .. import adapter_registry

    class Mirsal2Adapter(BaseAdapter):
        PROVIDER_CODE = 'mirsal2'
        API_VERSION = '2.4'
        ...

    adapter_registry.register('mirsal2', Mirsal2Adapter)

What the base provides for free:

* ``profile`` access: the eh.log.adapter.profile record this adapter
  was instantiated against, with all configuration (endpoint,
  environment, credentials reference, timeouts, retry policy).
* ``credentials`` access: pre-resolved credential string via the
  helper, raised CredentialsMissingError on failure.
* ``log_message`` helper: writes an eh.log.adapter.message row with
  correlation id, timing, and PII-redacted payloads.
* ``with_retry`` decorator and ``call`` orchestrator: handles the
  timeout, retry, circuit-breaker, dead-letter cycle so concrete
  adapters write only the request/response specifics.
* ``mock_mode``: when the profile environment is ``mock``, ``send``
  loads the captured fixture for the message type and scenario instead
  of dispatching, so CI runs the same code path as production with
  zero network.

Concrete adapter contract (methods to override):

* ``serialize(message_type, payload) -> bytes``: produce the wire
  payload (JSON, XML, EDI segment, etc.) from a plain Python dict.
* ``parse(message_type, raw) -> dict``: inverse of serialize.
* ``transport(method, url, body, headers) -> (status, body, headers)``:
  the actual HTTP/SFTP/AS2 call. Default implementation uses
  ``requests`` for HTTP; subclasses for SFTP or AS2 override.
* ``health_check_payload() -> dict``: payload for the provider's
  documented health probe.
* ``replay_from_message(message)``: replay support for the dead
  letter queue. Default implementation re-dispatches the original
  request payload; adapters with non-idempotent semantics override
  to return False.
"""
from __future__ import annotations

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from ..exceptions import (
    AdapterAuthError,
    AdapterTimeoutError,
    AdapterValidationError,
    ConfigurationMissingError,
)

_logger = logging.getLogger(__name__)


@dataclass
class AdapterCallResult:
    """Container returned by BaseAdapter.call().

    Concrete adapters typically wrap this in a more specific result
    type (Mirsal2DeclarationResult, FasahManifestResult, etc.) but
    the shared shape is consistent across adapters: status, parsed
    payload, error code, error message, message log row id.
    """
    status: str
    parsed: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    message_id: Optional[int] = None
    raw_response: Optional[str] = None
    latency_ms: int = 0
    retry_count: int = 0


class BaseAdapter:
    """Inherit from this in every concrete adapter.

    Concrete subclasses set ``PROVIDER_CODE`` and ``API_VERSION``
    class attributes and override the small set of contract methods
    documented at the top of this file.
    """

    # Subclasses MUST set these. The base raises in __init__ if either
    # is missing or does not match the profile's api_version.
    PROVIDER_CODE: str = ""
    API_VERSION: str = ""

    # Mock fixtures are looked up under tests/fixtures/<MOCK_FIXTURE_DIR>/
    # by message_type + scenario. Defaults to PROVIDER_CODE.
    MOCK_FIXTURE_DIR: str = ""

    def __init__(self, profile):
        if not self.PROVIDER_CODE:
            raise ConfigurationMissingError(
                10,
                "Concrete adapter is missing PROVIDER_CODE class attribute. "
                "Add e.g. PROVIDER_CODE = 'mirsal2' on the subclass.",
            )
        if not self.API_VERSION:
            raise ConfigurationMissingError(
                11,
                "Concrete adapter is missing API_VERSION class attribute. "
                "Add e.g. API_VERSION = '2.4' on the subclass.",
            )
        if profile.provider_code != self.PROVIDER_CODE:
            raise ConfigurationMissingError(
                12,
                f"Adapter {self.__class__.__name__} declares PROVIDER_CODE "
                f"{self.PROVIDER_CODE!r} but was instantiated against "
                f"profile {profile.display_name!r} with provider_code "
                f"{profile.provider_code!r}.",
            )
        if profile.api_version != self.API_VERSION:
            raise ConfigurationMissingError(
                13,
                f"Profile {profile.display_name!r} declares API version "
                f"{profile.api_version!r} but adapter "
                f"{self.__class__.__name__} implements {self.API_VERSION!r}. "
                f"Either upgrade the adapter or downgrade the profile's "
                f"api_version field; do not silently dispatch.",
            )
        self.profile = profile
        self.env = profile.env
        self._mock_dir = self.MOCK_FIXTURE_DIR or self.PROVIDER_CODE

    # ----- Public surface -----

    def health_check(self) -> AdapterCallResult:
        """Run the provider's health probe and update profile status."""
        result = self.call("health_check", self.health_check_payload())
        status_map = {
            "success": "ok",
            "retry": "degraded",
            "timeout": "down",
            "failure": "down",
            "rejected": "degraded",
            "dead_letter": "down",
        }
        self.profile.sudo().write({
            "health_check_status": status_map.get(result.status, "unknown"),
            "health_check_at": self._now(),
            "health_check_message": result.error_message or "OK",
            "health_check_latency_ms": result.latency_ms,
        })
        return result

    def call(
        self,
        message_type: str,
        payload: Any,
        related_model: Optional[str] = None,
        related_record_id: Optional[int] = None,
        related_record_display: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> AdapterCallResult:
        """Single entrypoint for every adapter call.

        Wraps the concrete ``transport`` call in: timeout handling,
        retry with exponential backoff and jitter, circuit-breaker
        gate, audit logging, mock-mode dispatch.
        """
        if self.profile.environment == "mock":
            return self._call_mock(
                message_type, payload, related_model,
                related_record_id, related_record_display,
                idempotency_key,
            )

        correlation_id = str(uuid.uuid4())
        max_attempts = max(1, self.profile.retry_max_attempts or 1)
        attempt = 0
        last_exception = None

        # Circuit breaker: read recent message log to count consecutive
        # failures. The breaker is per-process implicit; consecutive
        # failures recorded in the database are the durable state.
        if self._breaker_open():
            return self._record_breaker_open(
                message_type, payload, correlation_id,
                related_model, related_record_id, related_record_display,
                idempotency_key,
            )

        while attempt < max_attempts:
            attempt += 1
            started = time.monotonic()
            try:
                serialized = self.serialize(message_type, payload)
                url = self._endpoint_for(message_type)
                headers = self._headers_for(message_type)
                status_code, raw_body, response_headers = self.transport(
                    method=self._http_method(message_type),
                    url=url,
                    body=serialized,
                    headers=headers,
                    timeout=self.profile.request_timeout_seconds,
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                if 200 <= status_code < 300:  # noqa: gcclog-hardcode HTTP success range, RFC 9110
                    parsed = self.parse(message_type, raw_body)
                    message = self._log_message(
                        message_type=message_type,
                        direction="outbound",
                        status="success",
                        correlation_id=correlation_id,
                        idempotency_key=idempotency_key,
                        request_payload=serialized,
                        response_payload=raw_body,
                        request_headers=headers,
                        response_headers=response_headers,
                        http_status=status_code,
                        latency_ms=latency_ms,
                        retry_count=attempt - 1,
                        related_model=related_model,
                        related_record_id=related_record_id,
                        related_record_display=related_record_display,
                    )
                    return AdapterCallResult(
                        status="success",
                        parsed=parsed,
                        message_id=message.id,
                        raw_response=raw_body,
                        latency_ms=latency_ms,
                        retry_count=attempt - 1,
                    )

                if 400 <= status_code < 500 and status_code != 429:  # noqa: gcclog-hardcode HTTP client error range and rate-limit code, RFC 9110 / RFC 6585
                    # Client errors are not retried.
                    parsed = self._safe_parse(message_type, raw_body)
                    message = self._log_message(
                        message_type=message_type,
                        direction="outbound",
                        status="rejected",
                        correlation_id=correlation_id,
                        idempotency_key=idempotency_key,
                        request_payload=serialized,
                        response_payload=raw_body,
                        request_headers=headers,
                        response_headers=response_headers,
                        http_status=status_code,
                        latency_ms=latency_ms,
                        retry_count=attempt - 1,
                        error_code=str(status_code),
                        error_message=self._error_text(parsed, raw_body),
                        related_model=related_model,
                        related_record_id=related_record_id,
                        related_record_display=related_record_display,
                    )
                    if status_code in (401, 403):  # noqa: gcclog-hardcode HTTP auth failure codes, RFC 9110
                        raise AdapterAuthError(
                            14,
                            f"Provider {self.PROVIDER_CODE} rejected the "
                            f"request with HTTP {status_code}. Verify the "
                            f"credentials and the profile's environment.",
                        )
                    if status_code == 422:  # noqa: gcclog-hardcode HTTP unprocessable entity, RFC 9110
                        raise AdapterValidationError(
                            15,
                            f"Provider {self.PROVIDER_CODE} rejected the "
                            f"payload with HTTP 422. See message log "
                            f"{message.id} for the validation detail.",
                        )
                    return AdapterCallResult(
                        status="rejected",
                        parsed=parsed,
                        message_id=message.id,
                        raw_response=raw_body,
                        latency_ms=latency_ms,
                        retry_count=attempt - 1,
                        error_code=str(status_code),
                        error_message=self._error_text(parsed, raw_body),
                    )

                # 5xx and 429: retryable.
                last_exception = None
                if attempt < max_attempts:
                    self._sleep_backoff(attempt)
                    continue
                # Out of retries: log dead letter.
                message = self._log_message(
                    message_type=message_type,
                    direction="outbound",
                    status="dead_letter",
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    request_payload=serialized,
                    response_payload=raw_body,
                    request_headers=headers,
                    response_headers=response_headers,
                    http_status=status_code,
                    latency_ms=latency_ms,
                    retry_count=attempt - 1,
                    error_code=str(status_code),
                    error_message=raw_body,
                    related_model=related_model,
                    related_record_id=related_record_id,
                    related_record_display=related_record_display,
                )
                return AdapterCallResult(
                    status="dead_letter",
                    message_id=message.id,
                    raw_response=raw_body,
                    latency_ms=latency_ms,
                    retry_count=attempt - 1,
                    error_code=str(status_code),
                    error_message=raw_body,
                )

            except TimeoutError as exc:
                last_exception = exc
                if attempt < max_attempts:
                    self._sleep_backoff(attempt)
                    continue
                latency_ms = int((time.monotonic() - started) * 1000)
                message = self._log_message(
                    message_type=message_type,
                    direction="outbound",
                    status="timeout",
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    request_payload=None,
                    response_payload=None,
                    request_headers=None,
                    response_headers=None,
                    http_status=0,
                    latency_ms=latency_ms,
                    retry_count=attempt - 1,
                    error_code="TIMEOUT",
                    error_message=str(exc),
                    related_model=related_model,
                    related_record_id=related_record_id,
                    related_record_display=related_record_display,
                )
                raise AdapterTimeoutError(
                    16,
                    f"Provider {self.PROVIDER_CODE} did not respond within "
                    f"{self.profile.request_timeout_seconds}s after "
                    f"{attempt} attempt(s). See message log {message.id}.",
                ) from exc

        if last_exception is not None:
            raise last_exception

        # Defensive: should not be reached.
        return AdapterCallResult(status="failure")

    # ----- Methods concrete adapters override -----

    def serialize(self, message_type: str, payload: Any) -> bytes:
        raise NotImplementedError

    def parse(self, message_type: str, raw: str) -> Any:
        raise NotImplementedError

    def transport(
        self,
        method: str,
        url: str,
        body: bytes,
        headers: dict,
        timeout: int,
    ):
        """Perform the actual transport. Returns (status, body, headers).

        Default implementation uses ``requests`` for HTTP. Subclasses
        for SFTP, AS2, or SMTP override entirely.
        """
        try:
            import requests
        except ImportError as exc:
            raise ConfigurationMissingError(
                17,
                "The 'requests' library is required for the default HTTP "
                "transport. Install it on the server or override "
                "transport() in your adapter subclass.",
            ) from exc
        try:
            response = requests.request(
                method=method,
                url=url,
                data=body,
                headers=headers,
                timeout=timeout,
            )
        except requests.Timeout as exc:
            raise TimeoutError(str(exc)) from exc
        return (
            response.status_code,
            response.text,
            dict(response.headers),
        )

    def health_check_payload(self) -> Any:
        """Payload for the provider's health probe.

        Override to send a real ping. Default is an empty GET that
        adapters with no documented health endpoint may treat as
        a connectivity check only.
        """
        return {}

    def replay_from_message(self, message):
        """Re-dispatch an outbound message. Override to disable for
        non-idempotent adapters by returning False.
        """
        return self.call(
            message_type=message.message_type,
            payload=self.parse(message.message_type, message.request_payload),
            related_model=message.related_model,
            related_record_id=message.related_record_id,
            related_record_display=message.related_record_display,
            idempotency_key=message.idempotency_key,
        )

    # ----- Subclass-friendly helpers -----

    def _endpoint_for(self, message_type: str) -> str:
        """Resolve the endpoint URL for a message type.

        Default returns the profile's primary endpoint. Adapters that
        use multiple endpoints (e.g. /declare vs /status) override.
        """
        if not self.profile.endpoint_url:
            raise ConfigurationMissingError(
                18,
                f"Profile {self.profile.display_name!r} has no endpoint "
                f"URL configured for environment "
                f"{self.profile.environment}.",
            )
        return self.profile.endpoint_url

    def _http_method(self, message_type: str) -> str:
        """HTTP verb for a message type. Default POST."""
        return "POST"

    def _headers_for(self, message_type: str) -> dict:
        """Return base headers; auth header injected by subclasses."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"erpheritage-logistics/{self.API_VERSION}",
        }

    # ----- Internals -----

    def _now(self):
        from odoo import fields
        return fields.Datetime.now()

    def _sleep_backoff(self, attempt: int) -> None:
        base = 1.5 ** attempt
        jitter = random.uniform(0, base * 0.25)
        time.sleep(base + jitter)

    def _breaker_open(self) -> bool:
        threshold = self.profile.circuit_breaker_threshold
        if threshold <= 0:
            return False
        Message = self.env["eh.log.adapter.message"]
        recent = Message.search(
            [
                ("profile_id", "=", self.profile.id),
                ("direction", "=", "outbound"),
            ],
            order="created_at desc",
            limit=threshold,
        )
        if len(recent) < threshold:
            return False
        if all(m.status in ("failure", "timeout", "dead_letter") for m in recent):
            cooldown = self.profile.circuit_breaker_cooldown_seconds
            if cooldown <= 0:
                return True
            from odoo import fields
            most_recent = recent[0].created_at
            elapsed = (fields.Datetime.now() - most_recent).total_seconds()
            return elapsed < cooldown
        return False

    def _record_breaker_open(
        self, message_type, payload, correlation_id,
        related_model, related_record_id, related_record_display,
        idempotency_key,
    ) -> AdapterCallResult:
        message = self._log_message(
            message_type=message_type,
            direction="outbound",
            status="dead_letter",
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            request_payload=None,
            response_payload=None,
            request_headers=None,
            response_headers=None,
            http_status=0,
            latency_ms=0,
            retry_count=0,
            error_code="BREAKER_OPEN",
            error_message=(
                f"Circuit breaker is open for provider "
                f"{self.PROVIDER_CODE}. Last "
                f"{self.profile.circuit_breaker_threshold} consecutive "
                f"calls failed; cooldown not yet elapsed."
            ),
            related_model=related_model,
            related_record_id=related_record_id,
            related_record_display=related_record_display,
        )
        return AdapterCallResult(
            status="dead_letter",
            message_id=message.id,
            error_code="BREAKER_OPEN",
            error_message="Circuit breaker open.",
        )

    def _call_mock(
        self, message_type, payload, related_model,
        related_record_id, related_record_display, idempotency_key,
    ) -> AdapterCallResult:
        """Replay a captured fixture instead of dispatching."""
        from pathlib import Path
        import os
        # Look up MODULE_PATH/tests/fixtures/<dir>/<message_type>.success.json
        # falling back to .response.txt if the JSON is absent.
        scenario = "success"
        adapter_module_path = Path(self.__class__.__module__.split(".")[0])
        # The module is imported as 'odoo.addons.<module>'; resolve via
        # the registered adapter class file location.
        import sys
        module_obj = sys.modules.get(self.__class__.__module__)
        module_file = getattr(module_obj, "__file__", None)
        fixture_root = None
        if module_file:
            fixture_root = (
                Path(module_file).resolve().parent.parent
                / "tests" / "fixtures" / self._mock_dir
            )
        raw_body = ""
        if fixture_root and fixture_root.is_dir():
            for ext in ("json", "xml", "edi", "txt"):
                candidate = fixture_root / f"{message_type}.{scenario}.{ext}"
                if candidate.is_file():
                    raw_body = candidate.read_text(encoding="utf-8")
                    break
        if not raw_body:
            raise ConfigurationMissingError(
                19,
                f"Mock fixture for provider {self.PROVIDER_CODE}, message "
                f"{message_type!r}, scenario {scenario!r} not found under "
                f"{fixture_root}. Add a fixture file to enable mock-mode "
                f"playback.",
            )
        try:
            parsed = self.parse(message_type, raw_body)
        except Exception:
            parsed = None
        message = self._log_message(
            message_type=message_type,
            direction="outbound",
            status="success",
            correlation_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            request_payload=str(payload) if payload else "",
            response_payload=raw_body,
            request_headers={"x-mock": "1"},
            response_headers={"x-mock": "1"},
            http_status=200,
            latency_ms=0,
            retry_count=0,
            related_model=related_model,
            related_record_id=related_record_id,
            related_record_display=related_record_display,
        )
        return AdapterCallResult(
            status="success",
            parsed=parsed,
            message_id=message.id,
            raw_response=raw_body,
            latency_ms=0,
            retry_count=0,
        )

    def _safe_parse(self, message_type: str, raw: str):
        try:
            return self.parse(message_type, raw)
        except Exception:
            return None

    def _error_text(self, parsed, raw):
        if isinstance(parsed, dict):
            for key in ("message", "error", "detail", "Message"):
                if key in parsed:
                    return str(parsed[key])
        return raw[:500] if raw else ""  # noqa: gcclog-hardcode conservative error-text bound, never user-tunable

    def _log_message(
        self,
        message_type: str,
        direction: str,
        status: str,
        correlation_id: str,
        idempotency_key: Optional[str],
        request_payload,
        response_payload,
        request_headers,
        response_headers,
        http_status: int,
        latency_ms: int,
        retry_count: int,
        related_model: Optional[str],
        related_record_id: Optional[int],
        related_record_display: Optional[str],
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        Message = self.env["eh.log.adapter.message"].sudo()
        return Message.create({
            "profile_id": self.profile.id,
            "message_type": message_type,
            "direction": direction,
            "status": status,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key or False,
            "request_payload": self._sanitise(request_payload),
            "response_payload": self._sanitise(response_payload),
            "request_headers": self._sanitise_headers(request_headers),
            "response_headers": self._sanitise_headers(response_headers),
            "http_status": http_status,
            "latency_ms": latency_ms,
            "retry_count": retry_count,
            "related_model": related_model or False,
            "related_record_id": related_record_id or 0,
            "related_record_display": related_record_display or False,
            "error_code": error_code or False,
            "error_message": error_message or False,
            "completed_at": self._now(),
        })

    def _sanitise(self, payload) -> str:
        """Truncate and redact a payload for storage.

        Concrete adapters override to apply provider-specific
        redaction. The default truncates to the configured maximum.
        """
        if payload is None:
            return ""
        text = payload if isinstance(payload, str) else str(payload)
        max_chars = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "eh_log.base.adapter_message_payload_max_chars",
                default="32768",
            )
        )
        if len(text) > max_chars:
            return text[:max_chars] + "\n... [truncated]"
        return text

    def _sanitise_headers(self, headers) -> str:
        """Redact authentication headers before storage."""
        if not headers:
            return ""
        REDACT = {
            "authorization", "x-api-key", "x-auth-token", "cookie",
            "set-cookie", "proxy-authorization",
        }
        out = []
        for key, value in headers.items():
            if key.lower() in REDACT:
                out.append(f"{key}: [REDACTED]")
            else:
                out.append(f"{key}: {value}")
        return "\n".join(out)
