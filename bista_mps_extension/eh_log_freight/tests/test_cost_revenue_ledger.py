# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Cost and revenue ledger: amount computation, actuals, margin drift."""
from .common import EhLogFreightTestCase


class TestCostRevenueLedger(EhLogFreightTestCase):

    def setUp(self):
        super().setUp()
        order = self._build_logistics_sale_order()
        self.job = self._confirm_and_get_job(order)

    def test_actual_cost_excludes_cancelled(self):
        Cost = self.env["eh.log.freight.cost.line"]
        Cost.create({
            "job_id": self.job.id,
            "description": "Carrier freight",
            "quantity": 1.0,
            "unit_cost": 1100.0,
            "state": "invoiced",
        })
        Cost.create({
            "job_id": self.job.id,
            "description": "Cancelled adjustment",
            "quantity": 1.0,
            "unit_cost": 200.0,
            "state": "cancelled",
        })
        self.job.invalidate_recordset()
        self.assertEqual(self.job.total_actual_cost, 1100.0)

    def test_actual_revenue_excludes_disbursements(self):
        Revenue = self.env["eh.log.freight.revenue.line"]
        duty_code = self.env.ref("eh_log_base.charge_code_duty")
        Revenue.create({
            "job_id": self.job.id,
            "description": "Ocean Freight",
            "charge_code_id": self.charge_code_ofr.id,
            "quantity": 1.0,
            "unit_price": 1500.0,
            "state": "invoiced",
        })
        Revenue.create({
            "job_id": self.job.id,
            "description": "Customs Duty Pass-through",
            "charge_code_id": duty_code.id,
            "quantity": 1.0,
            "unit_price": 300.0,
            "state": "invoiced",
        })
        self.job.invalidate_recordset()
        self.assertEqual(self.job.total_actual_revenue, 1500.0)

    def test_margin_drift_negative_when_cost_overruns(self):
        Cost = self.env["eh.log.freight.cost.line"]
        Revenue = self.env["eh.log.freight.revenue.line"]
        # Planned (from quotation): rev 1500, cost 1100, margin pct ~26.67%
        Revenue.create({
            "job_id": self.job.id,
            "description": "Ocean Freight",
            "charge_code_id": self.charge_code_ofr.id,
            "quantity": 1.0,
            "unit_price": 1500.0,
            "state": "invoiced",
        })
        Cost.create({
            "job_id": self.job.id,
            "description": "Carrier freight overrun",
            "quantity": 1.0,
            "unit_cost": 1300.0,
            "state": "invoiced",
        })
        self.job.invalidate_recordset()
        self.assertAlmostEqual(self.job.actual_gross_margin, 200.0, places=2)
        # Drift = actual_pct - planned_pct < 0 because actual margin shrank.
        self.assertLess(self.job.margin_drift_pct, 0.0)

    def test_amount_computation(self):
        line = self.env["eh.log.freight.cost.line"].create({
            "job_id": self.job.id,
            "description": "Ten units at fifty",
            "quantity": 10.0,
            "unit_cost": 50.0,
        })
        self.assertEqual(line.amount, 500.0)
