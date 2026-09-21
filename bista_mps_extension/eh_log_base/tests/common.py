# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Shared test fixtures for the ERP Heritage logistics suite.

Two base classes:

* EhLogUnitTestCase: pure unit. No fixture seeding beyond what
  TransactionCase already provides. Use for exception hierarchy
  shape tests, credentials helper precedence tests, adapter base
  contract tests that work against an in-memory profile mock.
* EhLogIntegrationTestCase: integration. Seeds a partner, an adapter
  profile, a charge code, a document type so tests can compose
  realistic scenarios without re-seeding.

Both classes also wipe the adapter registry between tests so a
TestAdapter registered in one test does not leak into the next.
"""
from odoo.tests import TransactionCase

from .. import adapter_registry


class EhLogUnitTestCase(TransactionCase):
    """Lightweight base. No logistics fixtures."""

    def setUp(self):
        super().setUp()
        self._registry_snapshot = dict(adapter_registry._REGISTRY)
        self.addCleanup(self._restore_registry)

    def _restore_registry(self):
        adapter_registry.clear()
        for code, cls in self._registry_snapshot.items():
            adapter_registry.register(code, cls)


class EhLogIntegrationTestCase(TransactionCase):
    """Integration base with a seeded partner, profile, and master data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.partner_a = cls.env["res.partner"].create({
            "name": "Test Customer A",
            "is_company": True,
            "country_id": cls.env.ref("base.ae", raise_if_not_found=False).id
                if cls.env.ref("base.ae", raise_if_not_found=False) else False,
        })
        cls.partner_b = cls.env["res.partner"].create({
            "name": "Test Vendor B",
            "is_company": True,
        })

        cls.profile_test = cls.env["eh.log.adapter.profile"].create({
            "name": "Test Provider (Mock)",
            "provider_code": "test_provider",
            "provider_kind": "regulator",
            "environment": "mock",
            "api_version": "1.0",
            "auth_method": "api_key",
            "credential_purpose": "test.api_key",
            "endpoint_url": "https://example.test/api",
            "company_id": cls.company.id,
        })

        cls.charge_code_freight = cls.env.ref("eh_log_base.charge_code_ofr")
        cls.doc_type_hbl = cls.env.ref("eh_log_base.doc_type_hbl")

    def setUp(self):
        super().setUp()
        self._registry_snapshot = dict(adapter_registry._REGISTRY)
        self.addCleanup(self._restore_registry)

    def _restore_registry(self):
        adapter_registry.clear()
        for code, cls in self._registry_snapshot.items():
            adapter_registry.register(code, cls)
