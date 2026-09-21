# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Charge template: seeds, apply wizard, replace mode, line projection."""
from psycopg2 import IntegrityError
from odoo.tools.misc import mute_logger

from .common import EhLogQuotationTestCase


class TestChargeTemplate(EhLogQuotationTestCase):

    def test_seed_templates_present(self):
        self.assertTrue(
            self.env.ref("eh_log_quotation.charge_template_sea_fcl_default"),
        )
        self.assertTrue(
            self.env.ref("eh_log_quotation.charge_template_air_default"),
        )

    def test_template_code_unique(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["eh.log.charge.template"].create({
                    "code": "SEA-FCL-DEFAULT",
                    "name": "Duplicate code",
                    "mode": "sea",
                    "direction": "any",
                })

    def test_apply_template_appends_lines(self):
        before = len(self.order.order_line)
        wizard = self.env["eh.log.charge.template.apply"].create({
            "order_id": self.order.id,
            "template_id": self.template_sea.id,
            "replace_existing": False,
        })
        wizard.action_apply()
        self.order.invalidate_recordset()
        after = len(self.order.order_line)
        self.assertEqual(
            after - before,
            len(self.template_sea.line_ids),
            "Apply must add one sale order line per template line.",
        )
        self.assertTrue(self.order.eh_log_is_logistics)
        self.assertEqual(self.order.eh_log_charge_template_id, self.template_sea)
        self.assertEqual(self.order.eh_log_mode, "sea")

    def test_apply_template_replace_mode_drops_existing_charge_lines(self):
        # Seed an existing charge line and a non-charge product line.
        self._add_logistics_line(self.charge_code_othc, qty=1, price=50)
        self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "name": "Generic Service",
            "product_id": self.product_service.id,
            "product_uom_qty": 1.0,
            "price_unit": 100.0,
        })
        wizard = self.env["eh.log.charge.template.apply"].create({
            "order_id": self.order.id,
            "template_id": self.template_sea.id,
            "replace_existing": True,
        })
        wizard.action_apply()
        self.order.invalidate_recordset()
        # The OTHC charge line should have been removed; the product line preserved.
        product_lines = self.order.order_line.filtered(
            lambda l: l.product_id == self.product_service
        )
        self.assertEqual(
            len(product_lines), 1,
            "Replace mode must preserve non-logistics product lines.",
        )
        # The kept charge codes are exactly the template's codes.
        kept_codes = {
            l.eh_log_charge_code_id.id
            for l in self.order.order_line
            if l.eh_log_charge_code_id
        }
        template_codes = {
            l.charge_code_id.id for l in self.template_sea.line_ids
        }
        self.assertEqual(kept_codes, template_codes)
