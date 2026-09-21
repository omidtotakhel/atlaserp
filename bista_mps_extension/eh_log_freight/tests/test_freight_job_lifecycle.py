# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Job state machine: allowed transitions, write protection, audit log."""
from odoo.exceptions import UserError

from odoo.addons.eh_log_base.exceptions import JobStateConflictError

from .common import EhLogFreightTestCase


class TestFreightJobLifecycle(EhLogFreightTestCase):

    def setUp(self):
        super().setUp()
        order = self._build_logistics_sale_order()
        self.job = self._confirm_and_get_job(order)

    def test_initial_state_is_draft(self):
        self.assertEqual(self.job.state, "draft")
        self.assertTrue(self.job.name.startswith("FF/"))
        self.assertTrue(self.job.analytic_account_id)

    def test_full_happy_path(self):
        self.job.action_book()
        self.assertEqual(self.job.state, "booked")
        self.job.action_set_in_transit()
        self.assertEqual(self.job.state, "in_transit")
        self.job.action_set_at_destination()
        self.assertEqual(self.job.state, "at_destination")
        self.job.action_set_delivered()
        self.assertEqual(self.job.state, "delivered")
        self.assertTrue(self.job.delivered_at)
        self.job.action_close()
        self.assertEqual(self.job.state, "closed")
        self.assertTrue(self.job.closed_at)

    def test_disallowed_transition_raises(self):
        # Cannot jump from draft straight to delivered.
        with self.assertRaises(JobStateConflictError) as ctx:
            self.job.action_set_delivered()
        self.assertIn("[EHL-JOB-STATE-001]", str(ctx.exception))

    def test_direct_state_write_blocked(self):
        with self.assertRaises(UserError) as ctx:
            self.job.write({"state": "booked"})
        self.assertIn("[EHL-JOB-STATE-002]", str(ctx.exception))

    def test_cancel_from_in_transit(self):
        self.job.action_book()
        self.job.action_set_in_transit()
        self.job.action_cancel()
        self.assertEqual(self.job.state, "cancelled")

    def test_no_transition_from_cancelled(self):
        self.job.action_cancel()
        with self.assertRaises(JobStateConflictError):
            self.job.action_book()

    def test_audit_event_written_on_each_transition(self):
        before = self.env["eh.log.event"].search_count([
            ("category", "=", "state_transition"),
            ("related_model", "=", "eh.log.freight.job"),
            ("related_record_id", "=", self.job.id),
        ])
        self.job.action_book()
        after = self.env["eh.log.event"].search_count([
            ("category", "=", "state_transition"),
            ("related_model", "=", "eh.log.freight.job"),
            ("related_record_id", "=", self.job.id),
        ])
        self.assertEqual(after - before, 1)
