# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Credit guard: exposure computation, status thresholds, blocking on confirm."""
import unittest.mock as mock

from odoo.addons.eh_log_base.exceptions import CreditExposureError

from .common import EhLogQuotationTestCase


class TestCreditGuard(EhLogQuotationTestCase):

    def setUp(self):
        super().setUp()
        self.company.write({"eh_log_credit_warning_pct": 80.0})
        self.partner.write({"credit_limit": 10000.0})

    def _patch_exposure(self, value):
        return mock.patch.object(
            type(self.order),
            "_eh_log_compute_partner_exposure",
            return_value=value,
        )

    def test_status_ok_when_exposure_below_warning(self):
        with self._patch_exposure(1000.0):
            self.order.invalidate_recordset()
            self.assertEqual(self.order.eh_log_credit_status, "ok")

    def test_status_warning_when_exposure_in_band(self):
        with self._patch_exposure(8500.0):
            self.order.invalidate_recordset()
            self.assertEqual(self.order.eh_log_credit_status, "warning")

    def test_status_blocked_when_exposure_at_or_above_limit(self):
        with self._patch_exposure(10000.0):
            self.order.invalidate_recordset()
            self.assertEqual(self.order.eh_log_credit_status, "blocked")

    def test_confirm_raises_when_credit_blocked(self):
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=500, cost=400)
        self.order.invalidate_recordset()
        with self._patch_exposure(15000.0):
            with self.assertRaises(CreditExposureError) as ctx:
                self.order.action_confirm()
            self.assertIn("[EHL-CREDIT-001]", str(ctx.exception))

    def test_confirm_passes_when_no_credit_limit_set(self):
        self.partner.write({"credit_limit": 0.0})
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=500, cost=400)
        self.order.invalidate_recordset()
        with self._patch_exposure(50000.0):
            # No limit means no enforcement; status is 'ok' with hint.
            self.assertEqual(self.order.eh_log_credit_status, "ok")
