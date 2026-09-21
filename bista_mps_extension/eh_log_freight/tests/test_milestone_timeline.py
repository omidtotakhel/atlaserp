# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Milestone seeding, uniqueness, variance computation."""
from datetime import datetime, timedelta
from psycopg2 import IntegrityError
from odoo.tools.misc import mute_logger

from .common import EhLogFreightTestCase


class TestMilestoneTimeline(EhLogFreightTestCase):

    def setUp(self):
        super().setUp()
        order = self._build_logistics_sale_order(mode="sea")
        self.job = self._confirm_and_get_job(order)

    def test_required_milestones_seeded_for_sea(self):
        codes = self.job.milestone_ids.type_id.mapped("code")
        # Sea-mode required milestones from the seed data.
        for required in ("SEA_BOOKED", "SEA_GATE_IN", "SEA_LOADED",
                         "SEA_SAILED", "SEA_ARRIVED", "SEA_DISCHARGED",
                         "SEA_GATE_OUT", "POD_RECEIVED"):
            self.assertIn(required, codes,
                          f"Required milestone {required} missing from "
                          f"sea mode seeded job timeline.")

    def test_no_air_milestones_on_sea_job(self):
        codes = self.job.milestone_ids.type_id.mapped("code")
        for not_expected in ("AIR_DEPARTED", "AIR_ARRIVED"):
            self.assertNotIn(not_expected, codes)

    def test_milestone_uniqueness_per_job_type(self):
        type_booked = self.env.ref("eh_log_freight.ms_sea_booked")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["eh.log.freight.milestone"].create({
                    "job_id": self.job.id,
                    "type_id": type_booked.id,
                })

    def test_variance_computation(self):
        ms = self.job.milestone_ids.filtered(
            lambda m: m.type_id.code == "SEA_SAILED"
        )
        planned = datetime(2026, 6, 1, 10, 0)
        actual = planned + timedelta(hours=4, minutes=30)
        ms.write({
            "planned_at": planned,
            "actual_at": actual,
        })
        ms.invalidate_recordset()
        self.assertAlmostEqual(ms.variance_hours, 4.5, places=2)

    def test_variance_zero_when_either_side_missing(self):
        ms = self.job.milestone_ids[0]
        ms.write({
            "planned_at": False,
            "actual_at": datetime(2026, 6, 1, 12, 0),
        })
        ms.invalidate_recordset()
        self.assertEqual(ms.variance_hours, 0.0)
