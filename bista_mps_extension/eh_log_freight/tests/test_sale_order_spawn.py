# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Sale-order hook: job spawn on confirm, no double spawn, fields propagated."""
from .common import EhLogFreightTestCase


class TestSaleOrderSpawn(EhLogFreightTestCase):

    def test_confirm_spawns_one_freight_job(self):
        order = self._build_logistics_sale_order()
        order.action_confirm()
        order.invalidate_recordset()
        self.assertEqual(len(order.eh_log_freight_job_ids), 1)
        self.assertEqual(order.eh_log_freight_job_count, 1)

    def test_re_confirm_does_not_duplicate_job(self):
        order = self._build_logistics_sale_order()
        order.action_confirm()
        order._action_cancel()
        order.action_draft()
        order.action_confirm()
        order.invalidate_recordset()
        self.assertEqual(
            len(order.eh_log_freight_job_ids), 1,
            "Re-confirming an order that already has a freight job "
            "must not spawn a second one.",
        )

    def test_non_logistics_order_does_not_spawn(self):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "company_id": self.company.id,
        })
        product = self.env["product.product"].create({
            "name": "Generic", "type": "service",
        })
        self.env["sale.order.line"].create({
            "order_id": order.id,
            "name": "Generic line",
            "product_id": product.id,
            "product_uom_qty": 1.0,
            "price_unit": 100.0,
        })
        order.action_confirm()
        self.assertFalse(order.eh_log_freight_job_ids)

    def test_lane_fields_propagated_to_job(self):
        order = self._build_logistics_sale_order()
        job = self._confirm_and_get_job(order)
        self.assertEqual(job.mode, order.eh_log_mode)
        self.assertEqual(job.direction, order.eh_log_direction)
        self.assertEqual(job.origin_country_id, order.eh_log_origin_country_id)
        self.assertEqual(job.destination_country_id, order.eh_log_destination_country_id)
        self.assertEqual(job.origin_location, order.eh_log_origin_location)
        self.assertEqual(job.destination_location, order.eh_log_destination_location)
        self.assertEqual(job.customer_id, order.partner_id)

    def test_job_does_not_spawn_when_mode_missing(self):
        order = self._build_logistics_sale_order()
        order.eh_log_mode = False
        order.action_confirm()
        self.assertFalse(order.eh_log_freight_job_ids)
