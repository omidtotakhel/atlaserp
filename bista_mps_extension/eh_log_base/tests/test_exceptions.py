# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Exception hierarchy contract.

Verifies:

* Every typed exception inherits from the expected upstream Odoo class
  so the client renders it correctly.
* The error code prefix [EHL-<DOMAIN>-<NUMBER>] is present in every
  message so log greps work.
* Each exception exposes its code, domain, and body as attributes for
  test assertions and adapter handlers.
* The full set of typed exceptions is exported from the public
  ``__all__`` so a downstream module can ``from eh_log_base.exceptions
  import *`` without surprises.
"""
from odoo.exceptions import UserError, ValidationError

from .common import EhLogUnitTestCase
from .. import exceptions
from ..exceptions import (
    AdapterAuthError,
    AdapterTimeoutError,
    AdapterValidationError,
    AgreementVersionConflictError,
    CompanyMismatchError,
    ConfigurationMissingError,
    CredentialsMissingError,
    CreditExposureError,
    CustomsDeclarationError,
    EDIDispatchError,
    EhLogError,
    EhLogValidationError,
    JobStateConflictError,
    KYCExpiredError,
    RatingNotFoundError,
    RoutingError,
)


USER_ERROR_TYPES = [
    (KYCExpiredError, "KYC"),
    (CreditExposureError, "CREDIT"),
    (AgreementVersionConflictError, "AGREEMENT"),
    (CustomsDeclarationError, "CUSTOMS"),
    (RatingNotFoundError, "RATING"),
    (RoutingError, "ROUTING"),
    (EDIDispatchError, "EDI"),
    (AdapterAuthError, "ADAPTER-AUTH"),
    (AdapterTimeoutError, "ADAPTER-TIMEOUT"),
    (AdapterValidationError, "ADAPTER-VALIDATION"),
    (ConfigurationMissingError, "CONFIG"),
    (CredentialsMissingError, "CREDENTIALS"),
]

VALIDATION_ERROR_TYPES = [
    (JobStateConflictError, "JOB-STATE"),
    (CompanyMismatchError, "COMPANY"),
]


class TestExceptions(EhLogUnitTestCase):

    def test_user_error_inheritance(self):
        for cls, _domain in USER_ERROR_TYPES:
            self.assertTrue(
                issubclass(cls, EhLogError),
                f"{cls.__name__} must inherit from EhLogError.",
            )
            self.assertTrue(
                issubclass(cls, UserError),
                f"{cls.__name__} must inherit from UserError so the "
                f"Odoo client renders it as a friendly dialog.",
            )

    def test_validation_error_inheritance(self):
        for cls, _domain in VALIDATION_ERROR_TYPES:
            self.assertTrue(
                issubclass(cls, EhLogValidationError),
                f"{cls.__name__} must inherit from EhLogValidationError.",
            )
            self.assertTrue(
                issubclass(cls, ValidationError),
                f"{cls.__name__} must inherit from ValidationError so "
                f"the ORM rolls back the transaction.",
            )

    def test_user_error_message_format(self):
        for cls, domain in USER_ERROR_TYPES:
            instance = cls(42, "Test body for the message.")
            text = str(instance)
            self.assertTrue(
                text.startswith(f"[EHL-{domain}-042]"),
                f"{cls.__name__} message must start with the code prefix; "
                f"got: {text!r}",
            )
            self.assertIn(
                "Test body for the message.",
                text,
                f"{cls.__name__} message must include the body text.",
            )
            self.assertEqual(instance.code, 42)
            self.assertEqual(instance.domain, domain)
            self.assertEqual(instance.body, "Test body for the message.")

    def test_validation_error_message_format(self):
        for cls, domain in VALIDATION_ERROR_TYPES:
            instance = cls(7, "State X to Y is not allowed.")
            text = str(instance)
            self.assertTrue(
                text.startswith(f"[EHL-{domain}-007]"),
                f"{cls.__name__} message format mismatch: {text!r}",
            )
            self.assertEqual(instance.code, 7)
            self.assertEqual(instance.domain, domain)

    def test_all_exports(self):
        # Every typed exception we ship must be in __all__ so a
        # downstream module can import * without surprises.
        expected_names = {
            cls.__name__ for cls, _ in USER_ERROR_TYPES + VALIDATION_ERROR_TYPES
        }
        expected_names.update({
            "EhLogError",
            "EhLogValidationError",
            "UserError",
            "ValidationError",
            "AccessError",
            "RedirectWarning",
        })
        self.assertEqual(
            set(exceptions.__all__) & expected_names,
            expected_names,
            "exceptions.__all__ is missing one or more typed exceptions.",
        )

    def test_code_padding(self):
        # Three-digit zero-padded codes are required so log greps on
        # specific codes do not match unrelated suffix positions.
        instance = KYCExpiredError(5, "test")
        self.assertIn("[EHL-KYC-005]", str(instance))
        instance = KYCExpiredError(123, "test")
        self.assertIn("[EHL-KYC-123]", str(instance))
