# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Bill of lading: state machine, number requirement, uniqueness, hierarchy."""
from psycopg2 import IntegrityError
from odoo.exceptions import UserError
from odoo.tools.misc import mute_logger

from odoo.addons.eh_log_base.exceptions import JobStateConflictError

from .common import EhLogFreightTestCase


class TestBlLifecycle(EhLogFreightTestCase):

    def setUp(self):
        super().setUp()
        order = self._build_logistics_sale_order()
        self.job = self._confirm_and_get_job(order)

    def _make_bl(self, **overrides):
        vals = {
            "job_id": self.job.id,
            "bl_type": "hbl",
            "shipper_id": self.shipper.id,
            "consignee_id": self.consignee.id,
        }
        vals.update(overrides)
        return self.env["eh.log.freight.bl"].create(vals)

    def test_created_in_draft_with_sequence_reference(self):
        bl = self._make_bl()
        self.assertEqual(bl.state, "draft")
        self.assertTrue(bl.name.startswith("BL/"))

    def test_issue_requires_number(self):
        bl = self._make_bl()
        with self.assertRaises(UserError) as ctx:
            bl.action_issue()
        self.assertIn("[EHL-BL-001]", str(ctx.exception))

    def test_issue_then_release_then_close(self):
        bl = self._make_bl(number="MAEU1234567")
        bl.action_issue()
        self.assertEqual(bl.state, "issued")
        bl.action_release()
        self.assertEqual(bl.state, "released")
        bl.action_close()
        self.assertEqual(bl.state, "closed")

    def test_disallowed_transition_blocked(self):
        bl = self._make_bl(number="MAEU0000001")
        with self.assertRaises(JobStateConflictError) as ctx:
            bl.action_release()
        self.assertIn("[EHL-JOB-STATE-005]", str(ctx.exception))

    def test_direct_state_write_blocked(self):
        bl = self._make_bl()
        with self.assertRaises(UserError) as ctx:
            bl.write({"state": "issued"})
        self.assertIn("[EHL-BL-002]", str(ctx.exception))

    def test_number_unique_per_company_and_type(self):
        self._make_bl(number="MAEU2222222").action_issue()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._make_bl(number="MAEU2222222")

    def test_consolidation_hierarchy(self):
        mbl = self._make_bl(bl_type="mbl", number="MAEU5555555")
        hbl = self._make_bl(bl_type="hbl", number="HBL12345")
        hbl.parent_bl_id = mbl
        self.assertIn(hbl, mbl.child_bl_ids)
