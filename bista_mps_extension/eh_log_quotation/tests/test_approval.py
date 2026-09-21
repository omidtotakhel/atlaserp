# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Approval action: stamping, audit log entry, manager-only gating."""
from odoo.exceptions import UserError

from .common import EhLogQuotationTestCase


class TestApproval(EhLogQuotationTestCase):

    def setUp(self):
        super().setUp()
        # Drive the order into the approval-required state via margin floor.
        self.company.write({
            "eh_log_margin_warning_threshold": 15.0,
            "eh_log_margin_floor_threshold": 8.0,
        })
        self.order.write({"eh_log_is_logistics": True})
        self._add_logistics_line(self.charge_code_ofr, qty=1, price=1000, cost=950)
        self.order.invalidate_recordset()

    def test_setup_drives_approval_required(self):
        self.assertEqual(self.order.eh_log_margin_status, "below_floor")
        self.assertTrue(self.order.eh_log_requires_approval)
        self.assertFalse(self.order.eh_log_approved_by_id)

    def test_approve_stamps_user_and_timestamp(self):
        # Admin is in the manager group via the post_init_hook of eh_log_base.
        self.order.action_eh_log_approve()
        self.assertEqual(self.order.eh_log_approved_by_id, self.env.user)
        self.assertTrue(self.order.eh_log_approved_at)

    def test_approve_writes_audit_event(self):
        before = self.env["eh.log.event"].search_count([
            ("category", "=", "approval"),
            ("related_model", "=", "sale.order"),
            ("related_record_id", "=", self.order.id),
        ])
        self.order.action_eh_log_approve()
        after = self.env["eh.log.event"].search_count([
            ("category", "=", "approval"),
            ("related_model", "=", "sale.order"),
            ("related_record_id", "=", self.order.id),
        ])
        self.assertEqual(after - before, 1)

    def test_approve_rejected_when_not_required(self):
        # Drop cost so the order no longer needs approval.
        self.order.order_line[0].purchase_price = 700
        self.order.invalidate_recordset()
        self.assertFalse(self.order.eh_log_requires_approval)
        with self.assertRaises(UserError) as ctx:
            self.order.action_eh_log_approve()
        self.assertIn("[EHL-APPROVAL-002]", str(ctx.exception))

    def test_confirm_blocked_when_approval_required_and_missing(self):
        with self.assertRaises(UserError) as ctx:
            self.order.action_confirm()
        self.assertIn("[EHL-APPROVAL-003]", str(ctx.exception))

    def test_confirm_passes_after_approval(self):
        self.order.action_eh_log_approve()
        self.order.action_confirm()
        self.assertEqual(self.order.state, "sale")
