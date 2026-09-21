# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Margin guard: status transitions across the warning and floor thresholds."""
from .common import EhLogQuotationTestCase


class TestMarginGuard(EhLogQuotationTestCase):

    def setUp(self):
        super().setUp()
        # Pin thresholds so tests are stable regardless of company defaults.
        self.company.write({
            "eh_log_margin_warning_threshold": 15.0,
            "eh_log_margin_floor_threshold": 8.0,
        })

    def test_above_warning_when_margin_healthy(self):
        # Revenue 1000, cost 800 -> margin 200 -> 20%
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=800)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.eh_log_margin_status, "above_warning")
        self.assertAlmostEqual(self.order.eh_log_gross_margin_pct, 20.0, places=1)
        self.assertFalse(self.order.eh_log_requires_approval)

    def test_warning_band_when_margin_below_warning_above_floor(self):
        # Revenue 1000, cost 900 -> 10% -> warning band
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=900)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.eh_log_margin_status, "warning")
        self.assertFalse(self.order.eh_log_requires_approval)

    def test_below_floor_triggers_approval_requirement(self):
        # Revenue 1000, cost 950 -> 5% -> below floor
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=950)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.eh_log_margin_status, "below_floor")
        self.assertTrue(self.order.eh_log_requires_approval)
        self.assertIn(
            "below the company floor",
            self.order.eh_log_approval_reasons or "",
        )

    def test_disbursement_lines_do_not_dilute_margin(self):
        # Without disbursement: 1000 rev, 800 cost = 20% margin (above)
        # With added disbursement: 1200 rev seen by user, 1000 cost seen
        # but billable = 1000, billable cost = 800, so still 20%.
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=800)
        self._add_logistics_line(self.charge_code_duty, qty=1, price=200, cost=200)
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.order.eh_log_gross_margin_pct, 20.0, places=1)
        self.assertEqual(self.order.eh_log_margin_status, "above_warning")
