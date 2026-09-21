# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Shared fixtures for eh_log_freight tests."""
from odoo.tests import TransactionCase


class EhLogFreightTestCase(TransactionCase):
    """Seeds a customer, a shipper, a consignee, a confirmed logistics
    sale order, and the freight job spawned from it. Subclasses extend
    or modify per scenario.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({
            "name": "Test Logistics Customer",
            "is_company": True,
        })
        cls.shipper = cls.env["res.partner"].create({
            "name": "Test Shipper",
            "is_company": True,
        })
        cls.consignee = cls.env["res.partner"].create({
            "name": "Test Consignee",
            "is_company": True,
        })
        cls.charge_code_ofr = cls.env.ref("eh_log_base.charge_code_ofr")
        cls.country_cn = cls.env.ref("base.cn")
        cls.country_ae = cls.env.ref("base.ae")

    def _build_logistics_sale_order(self, mode="sea", direction="import", with_line=True):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "company_id": self.company.id,
            "eh_log_is_logistics": True,
            "eh_log_mode": mode,
            "eh_log_direction": direction,
            "eh_log_origin_country_id": self.country_cn.id,
            "eh_log_destination_country_id": self.country_ae.id,
            "eh_log_origin_location": "Shanghai",
            "eh_log_destination_location": "Jebel Ali",
        })
        if with_line:
            self.env["sale.order.line"].create({
                "order_id": order.id,
                "name": "Ocean Freight Shanghai - Jebel Ali",
                "product_uom_qty": 1.0,
                "price_unit": 1500.0,
                "eh_log_charge_code_id": self.charge_code_ofr.id,
                "purchase_price": 1100.0,
            })
        return order

    def _confirm_and_get_job(self, order):
        order.action_confirm()
        order.invalidate_recordset()
        self.assertEqual(len(order.eh_log_freight_job_ids), 1)
        return order.eh_log_freight_job_ids
