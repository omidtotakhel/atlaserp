# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Credentials helper precedence and error contract."""
import os
import unittest.mock as mock

from .common import EhLogUnitTestCase
from ..exceptions import CredentialsMissingError, ConfigurationMissingError


class TestCredentialsPrecedence(EhLogUnitTestCase):

    def test_env_var_wins_when_present(self):
        with mock.patch.dict(os.environ, {"EH_LOG_TEST_KEY": "from_env"}):
            value = self.env["eh.log.credentials"].get(
                "test_key",
                env_vars=["EH_LOG_TEST_KEY"],
                param_key="test.key",
            )
            self.assertEqual(value, "from_env")

    def test_first_env_var_wins(self):
        with mock.patch.dict(os.environ, {
            "EH_LOG_TEST_KEY": "first",
            "EH_LOG_TEST_FALLBACK": "second",
        }):
            value = self.env["eh.log.credentials"].get(
                "test_key",
                env_vars=["EH_LOG_TEST_KEY", "EH_LOG_TEST_FALLBACK"],
            )
            self.assertEqual(value, "first")

    def test_param_used_when_env_absent(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "eh_log.credentials.test.key", "from_param",
        )
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EH_LOG_TEST_KEY", None)
            value = self.env["eh.log.credentials"].get(
                "test_key",
                env_vars=["EH_LOG_TEST_KEY"],
                param_key="test.key",
            )
            self.assertEqual(value, "from_param")

    def test_default_used_when_neither_env_nor_param(self):
        os.environ.pop("EH_LOG_TEST_KEY", None)
        value = self.env["eh.log.credentials"].get(
            "test_key",
            env_vars=["EH_LOG_TEST_KEY"],
            param_key="test.no_such_key",
            default="default_value",
        )
        self.assertEqual(value, "default_value")

    def test_missing_credential_raises_typed_error(self):
        os.environ.pop("EH_LOG_TEST_MISSING", None)
        with self.assertRaises(CredentialsMissingError) as ctx:
            self.env["eh.log.credentials"].get(
                "test_missing",
                env_vars=["EH_LOG_TEST_MISSING"],
                param_key="test.missing",
            )
        message = str(ctx.exception)
        self.assertIn("[EHL-CREDENTIALS-001]", message)
        self.assertIn("test_missing", message)
        self.assertIn("EH_LOG_TEST_MISSING", message)
        self.assertIn("eh_log.credentials.test.missing", message)

    def test_per_company_param_takes_priority(self):
        company_id = self.env.company.id
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("eh_log.credentials.test.key", "global_value")
        ICP.set_param(
            f"eh_log.credentials.test.key.company.{company_id}",
            "company_value",
        )
        os.environ.pop("EH_LOG_TEST_KEY", None)
        value = self.env["eh.log.credentials"].get(
            "test_key",
            env_vars=["EH_LOG_TEST_KEY"],
            param_key="test.key",
            company_id=company_id,
        )
        self.assertEqual(value, "company_value")


class TestCredentialsEncryption(EhLogUnitTestCase):

    def setUp(self):
        super().setUp()
        try:
            import cryptography  # noqa: F401
            self.has_crypto = True
        except ImportError:
            self.has_crypto = False

    def test_round_trip_encryption(self):
        if not self.has_crypto:
            self.skipTest("cryptography library not installed")
        Credentials = self.env["eh.log.credentials"]
        Credentials.set_encrypted("test.encrypted_key", "secret_value")
        os.environ.pop("EH_LOG_TEST_ENC", None)
        value = Credentials.get(
            "encrypted_test",
            env_vars=["EH_LOG_TEST_ENC"],
            param_key="test.encrypted_key",
        )
        self.assertEqual(value, "secret_value")

    def test_encrypted_value_not_visible_in_param(self):
        if not self.has_crypto:
            self.skipTest("cryptography library not installed")
        self.env["eh.log.credentials"].set_encrypted(
            "test.secret_check", "supersecret",
        )
        raw = self.env["ir.config_parameter"].sudo().get_param(
            "eh_log.credentials.test.secret_check",
        )
        self.assertNotIn("supersecret", raw)
        self.assertTrue(raw.startswith("enc::v1::"))

    def test_set_encrypted_raises_when_crypto_missing(self):
        if self.has_crypto:
            self.skipTest("cryptography library is installed; cannot test missing path")
        with self.assertRaises(ConfigurationMissingError):
            self.env["eh.log.credentials"].set_encrypted(
                "test.no_crypto", "value",
            )
