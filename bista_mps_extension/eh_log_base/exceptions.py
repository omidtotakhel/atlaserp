# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Typed exception hierarchy for the ERP Heritage logistics suite.

Every domain failure raises a typed subclass so the UI, the logs, and
the test suite can route on type. Each exception carries a stable error
code that surfaces in the message prefix; support and ops use the code
to grep logs without parsing English.

Conventions:

* Subclass UserError when the user can self-correct (missing KYC,
  credit limit exceeded, missing rate). The Odoo client renders these
  as friendly dialogs.
* Subclass ValidationError for ORM-level invariants (constrains, save-
  time checks). The ORM rolls back the transaction.
* The error code prefix is mandatory: every message starts with
  "[EHL-<DOMAIN>-<NUMBER>]". A check in the tests asserts the prefix is
  present for every typed instance.
* Construct with `code` and `body`; the `__init__` formats the final
  message. Subclasses set their own DOMAIN; the numeric code is supplied
  by the caller from a domain-local constant table so test assertions
  can reference the constant rather than the literal number.
"""
from odoo.exceptions import (
    AccessError,
    RedirectWarning,
    UserError,
    ValidationError,
)


CODE_PREFIX = "EHL"


def _format(domain: str, code: int, body: str) -> str:
    """Compose the final user-facing string with the error code prefix.

    The prefix `[EHL-CUSTOMS-014]` is searchable in logs and in the
    user's screenshot to support. Body text is the actionable message;
    callers should already have wrapped it in `_()` for translation.
    """
    return f"[{CODE_PREFIX}-{domain.upper()}-{code:03d}] {body}"


class EhLogError(UserError):
    """Base class for ERP Heritage logistics user errors.

    Concrete subclasses set DOMAIN and pass an integer `code` plus a
    translated `body` string. The base class formats and stores both
    so callers can read `.code` and `.domain` off the exception in
    tests and adapter handlers.
    """

    DOMAIN = "BASE"

    def __init__(self, code: int, body: str):
        self.code = code
        self.domain = self.DOMAIN
        self.body = body
        super().__init__(_format(self.DOMAIN, code, body))


class EhLogValidationError(ValidationError):
    """Base class for ORM-level invariants that must roll back."""

    DOMAIN = "BASE"

    def __init__(self, code: int, body: str):
        self.code = code
        self.domain = self.DOMAIN
        self.body = body
        super().__init__(_format(self.DOMAIN, code, body))


# ----------------------------------------------------------------------
# Domain-specific user errors
# ----------------------------------------------------------------------


class KYCExpiredError(EhLogError):
    """Customer or vendor KYC document has expired.

    Surfaced when a quotation or job transition runs the pre-flight
    checklist and finds an expired KYC. The body should include the
    document type and expiry date.
    """

    DOMAIN = "KYC"


class CreditExposureError(EhLogError):
    """Quotation confirmation would exceed the customer credit limit.

    Body includes the current exposure, the proposed exposure, and the
    approved limit. UI offers to: reduce the quote, request a credit
    review, or take a security deposit.
    """

    DOMAIN = "CREDIT"


class AgreementVersionConflictError(EhLogError):
    """Two users edited the same agreement version concurrently.

    Body identifies the conflicting versions and points the user at the
    diff view to reconcile.
    """

    DOMAIN = "AGREEMENT"


class CustomsDeclarationError(EhLogError):
    """Customs declaration submission rejected at the regulator.

    Body includes the regulator-returned error message verbatim plus
    the local error code. The adapter logs the full payload to
    eh.log.adapter.message; the body links to that log entry.
    """

    DOMAIN = "CUSTOMS"


class RatingNotFoundError(EhLogError):
    """No rate sheet matched the lane and date for this quotation line.

    Never silently falls back to zero. UI offers a redirect to add a
    rate sheet or, for authorised users, a manual override path with
    audit log.
    """

    DOMAIN = "RATING"


class RoutingError(EhLogError):
    """Routing or geocoding provider could not resolve the request.

    Body indicates whether the fallback distance-matrix or great-circle
    estimate was used, and flags the resulting record so downstream
    decisions know the estimate quality is degraded.
    """

    DOMAIN = "ROUTING"


class EDIDispatchError(EhLogError):
    """EDI message dispatch failed at the transport layer.

    Body includes partner profile, message type, transport (AS2, SFTP,
    SMTP), and a pointer to the dead-letter entry. The originating
    record gains a manual retry button.
    """

    DOMAIN = "EDI"


class AdapterAuthError(EhLogError):
    """Adapter authentication failed against the configured profile.

    Body distinguishes "credentials missing" from "credentials rejected"
    and points to the credentials helper documentation.
    """

    DOMAIN = "ADAPTER-AUTH"


class AdapterTimeoutError(EhLogError):
    """Adapter call exceeded its configured timeout.

    The circuit breaker increments its failure counter; subsequent
    calls may be short-circuited until the half-open probe succeeds.
    Body includes the timeout value and current breaker state.
    """

    DOMAIN = "ADAPTER-TIMEOUT"


class AdapterValidationError(EhLogError):
    """Adapter received a payload it could not parse against the schema.

    Body includes the schema name, the failing field path, and the
    correlation id. The raw payload sits in eh.log.adapter.message
    with PII redacted per the profile's redaction rules.
    """

    DOMAIN = "ADAPTER-VALIDATION"


class ConfigurationMissingError(EhLogError):
    """A required ir.config_parameter or master data record is absent.

    Distinct from RatingNotFoundError because this is a setup-time
    failure, not a per-quotation gap. Body names the missing record
    and the screen where it is configured.
    """

    DOMAIN = "CONFIG"


class CredentialsMissingError(EhLogError):
    """The credentials helper could not resolve a required secret.

    Body lists the lookup precedence (env var, encrypted parameter,
    default) so the operator knows where to set the value. Always
    raised by the credentials helper, never by adapters directly.
    """

    DOMAIN = "CREDENTIALS"


# ----------------------------------------------------------------------
# Validation errors
# ----------------------------------------------------------------------


class JobStateConflictError(EhLogValidationError):
    """A state transition was attempted from an incompatible state.

    Raised by the state-machine guards in the operational models. Body
    names the source state, the target state, and the allowed
    transitions from the source.
    """

    DOMAIN = "JOB-STATE"


class CompanyMismatchError(EhLogValidationError):
    """A relation crosses companies in a way that breaks isolation.

    Raised when, e.g., a job in company A points to a charge code only
    visible to company B. Body identifies both companies and the
    offending field.
    """

    DOMAIN = "COMPANY"


# ----------------------------------------------------------------------
# Re-exports
# ----------------------------------------------------------------------

# Re-export the upstream Odoo exceptions for callers that want a single
# import point. Adapter handlers commonly catch AccessError or raise
# RedirectWarning; importing them from this module keeps the import
# block coherent with the typed errors above.
__all__ = (
    "AccessError",
    "RedirectWarning",
    "UserError",
    "ValidationError",
    "EhLogError",
    "EhLogValidationError",
    "KYCExpiredError",
    "CreditExposureError",
    "AgreementVersionConflictError",
    "CustomsDeclarationError",
    "RatingNotFoundError",
    "RoutingError",
    "EDIDispatchError",
    "AdapterAuthError",
    "AdapterTimeoutError",
    "AdapterValidationError",
    "ConfigurationMissingError",
    "CredentialsMissingError",
    "JobStateConflictError",
    "CompanyMismatchError",
)
