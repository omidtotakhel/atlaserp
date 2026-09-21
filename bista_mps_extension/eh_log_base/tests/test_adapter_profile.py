# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Adapter profile constraints, computes, and dispatch."""
from psycopg2 import IntegrityError
from odoo.tools.misc import mute_logger

from .common import EhLogIntegrationTestCase
from ..exceptions import ConfigurationMissingError


class TestAdapterProfile(EhLogIntegrationTestCase):

    def test_unique_per_provider_company_environment(self):
        # Cannot create a second profile for the same triple.
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["eh.log.adapter.profile"].create({
                    "name": "Duplicate",
                    "provider_code": "test_provider",
                    "provider_kind": "regulator",
                    "environment": "mock",
                    "api_version": "1.0",
                    "auth_method": "api_key",
                    "credential_purpose": "test.api_key",
                    "company_id": self.company.id,
                })

    def test_different_environment_allowed(self):
        # Same provider, same company, different environment is fine.
        sandbox = self.env["eh.log.adapter.profile"].create({
            "name": "Test Provider (Sandbox)",
            "provider_code": "test_provider",
            "provider_kind": "regulator",
            "environment": "sandbox",
            "api_version": "1.0",
            "auth_method": "api_key",
            "credential_purpose": "test.api_key",
            "endpoint_url": "https://sandbox.example/api",
            "company_id": self.company.id,
        })
        self.assertTrue(sandbox.id)
        self.assertEqual(sandbox.environment, "sandbox")

    def test_display_name_includes_environment(self):
        self.assertIn("Mock", self.profile_test.display_name)
        self.assertIn("Test Provider", self.profile_test.display_name)

    def test_company_ids_mirrors_company_id(self):
        self.assertEqual(
            self.profile_test.company_ids, self.profile_test.company_id,
            "company_ids m2m must mirror the company_id m2o for "
            "isolation rule consistency.",
        )

    def test_health_check_dispatch_requires_registered_adapter(self):
        with self.assertRaises(ConfigurationMissingError) as ctx:
            self.profile_test.action_run_health_check()
        message = str(ctx.exception)
        self.assertIn("[EHL-CONFIG-005]", message)
        self.assertIn("test_provider", message)

    def test_message_count_starts_zero(self):
        self.assertEqual(self.profile_test.message_count, 0)
        self.assertFalse(self.profile_test.last_message_at)

    def test_message_count_increments(self):
        Message = self.env["eh.log.adapter.message"]
        Message.create({
            "profile_id": self.profile_test.id,
            "correlation_id": "test-1",
            "message_type": "ping",
            "direction": "outbound",
            "status": "success",
        })
        Message.create({
            "profile_id": self.profile_test.id,
            "correlation_id": "test-2",
            "message_type": "ping",
            "direction": "outbound",
            "status": "success",
        })
        self.profile_test.invalidate_recordset()
        self.assertEqual(self.profile_test.message_count, 2)

    def test_suggested_env_vars_format(self):
        suggestions = self.profile_test._suggested_env_vars()
        self.assertEqual(suggestions[0], "EH_LOG_TEST_PROVIDER_TEST_API_KEY")
        self.assertEqual(suggestions[1], "EH_LOG_TEST_PROVIDER")

    def test_param_key_format(self):
        self.assertEqual(
            self.profile_test._param_key(),
            "test_provider.test.api_key",
        )
