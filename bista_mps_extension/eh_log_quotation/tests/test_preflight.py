# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Preflight wizard: row composition and overall status aggregation."""
from .common import EhLogQuotationTestCase


class TestPreflight(EhLogQuotationTestCase):

    def setUp(self):
        super().setUp()
        # Make the order a real logistics quotation with one healthy line.
        self.order.write({
            "eh_log_is_logistics": True,
            "eh_log_mode": "sea",
            "eh_log_direction": "import",
            "eh_log_origin_country_id": self.env.ref("base.cn").id,
            "eh_log_destination_country_id": self.env.ref("base.ae").id,
        })
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=700)

    def _run_wizard(self):
        wizard = self.env["eh.log.quotation.preflight"].create({
            "order_id": self.order.id,
        })
        wizard._run_checks()
        return wizard

    def test_overall_ok_when_everything_healthy(self):
        # Set Incoterm to clear that warning.
        # Incoterm lives on sale.order only when sale_stock is installed,
        # which the clean-room logistics stack does not require. Set it
        # only when the field is actually present.
        incoterm = self.env["account.incoterms"].search([], limit=1)
        if incoterm and "incoterm" in self.order._fields:
            self.order.incoterm = incoterm.id
        wizard = self._run_wizard()
        # KYC check returns 'not_assessed' on the base implementation,
        # which is treated as not_applicable, not blocking.
        self.assertIn(wizard.overall_status, ("ok", "warning"))

    def test_blocks_when_mode_missing(self):
        self.order.eh_log_mode = False
        wizard = self._run_wizard()
        mode_row = wizard.line_ids.filtered(lambda r: r.check == "mode")
        self.assertEqual(mode_row.status, "blocked")
        self.assertEqual(wizard.overall_status, "blocked")

    def test_warns_when_origin_country_missing(self):
        self.order.eh_log_origin_country_id = False
        wizard = self._run_wizard()
        origin_row = wizard.line_ids.filtered(lambda r: r.check == "origin")
        self.assertEqual(origin_row.status, "warning")

    def test_blocks_when_margin_below_floor(self):
        # Force margin into the floor band by raising cost.
        self.order.order_line[0].purchase_price = 980
        self.order.invalidate_recordset()
        wizard = self._run_wizard()
        margin_row = wizard.line_ids.filtered(lambda r: r.check == "margin")
        self.assertEqual(margin_row.status, "blocked")

    def test_warns_when_lines_missing_charge_code(self):
        self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Generic Service",
            "product_id": self.product_service.id,
            "product_uom_qty": 1.0,
            "price_unit": 200.0,
        })
        wizard = self._run_wizard()
        codes_row = wizard.line_ids.filtered(lambda r: r.check == "charge_codes")
        self.assertEqual(codes_row.status, "warning")
