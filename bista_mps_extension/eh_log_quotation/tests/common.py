# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Shared fixtures for eh_log_quotation tests."""
from odoo.tests import TransactionCase


class EhLogQuotationTestCase(TransactionCase):
    """Seeds a customer, a product (for non-logistics line tests), the
    OFR charge code, a sea-FCL charge template, and a draft sale order.
    Subclasses extend or modify per scenario.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Logistics Customer",
            "is_company": True,
            "credit_limit": 100000.0,
        })
        cls.product_service = cls.env["product.product"].create({
            "name": "Logistics Service",
            "type": "service",
        })
        cls.charge_code_ofr = cls.env.ref("eh_log_base.charge_code_ofr")
        cls.charge_code_othc = cls.env.ref("eh_log_base.charge_code_othc")
        cls.charge_code_dthc = cls.env.ref("eh_log_base.charge_code_dthc")
        cls.charge_code_duty = cls.env.ref("eh_log_base.charge_code_duty")  # disbursement
        cls.template_sea = cls.env.ref(
            "eh_log_quotation.charge_template_sea_fcl_default",
        )
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "company_id": cls.company.id,
        })

    def _add_logistics_line(self, charge_code, qty=1.0, price=100.0, cost=80.0):
        return self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": charge_code.name,
            "product_uom_qty": qty,
            "price_unit": price,
            "eh_log_charge_code_id": charge_code.id,
            "purchase_price": cost,
        })
