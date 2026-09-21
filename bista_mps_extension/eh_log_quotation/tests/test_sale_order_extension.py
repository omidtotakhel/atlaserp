# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""sale.order extension fields and onchange behaviour."""
from .common import EhLogQuotationTestCase


class TestSaleOrderExtension(EhLogQuotationTestCase):

    def test_logistics_flag_auto_set_when_charge_code_added(self):
        self.assertFalse(self.order.eh_log_is_logistics)
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=800)
        self.order.invalidate_recordset()
        self.assertTrue(
            self.order.eh_log_is_logistics,
            "Adding a line carrying a logistics charge code must auto-flag "
            "the parent order as a logistics quotation.",
        )

    def test_logistics_flag_not_set_for_pure_product_order(self):
        self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Generic Service",
            "product_id": self.product_service.id,
            "product_uom_qty": 1.0,
            "price_unit": 500.0,
        })
        self.assertFalse(self.order.eh_log_is_logistics)

    def test_disbursement_excluded_from_revenue_total(self):
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=800)
        self._add_logistics_line(self.charge_code_duty, qty=1, price=200, cost=200)
        self.order.invalidate_recordset()
        self.assertEqual(
            self.order.eh_log_total_revenue_billable, 1000.0,
            "Disbursement lines (DUTY here) must be excluded from the "
            "billable revenue used by the margin computation.",
        )

    def test_charge_code_onchange_sets_line_currency_default(self):
        line = self.env["sale.order.line"].new({
            "order_id": self.order.id,
            "eh_log_charge_code_id": self.charge_code_ofr.id,
        })
        line._onchange_eh_log_charge_code_id()
        self.assertEqual(line.name, self.charge_code_ofr.name)
