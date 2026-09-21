# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Event log: write protection and helper API."""
import json

from odoo.exceptions import UserError

from .common import EhLogIntegrationTestCase


class TestEventLog(EhLogIntegrationTestCase):

    def test_log_helper_creates_event(self):
        Event = self.env["eh.log.event"]
        event = Event.log(
            category="state_transition",
            summary="Job moved from draft to confirmed.",
            severity="info",
            related_model="eh.log.adapter.profile",
            related_record_id=self.profile_test.id,
            related_record_display=self.profile_test.display_name,
            context={"old_state": "draft", "new_state": "confirmed"},
        )
        self.assertTrue(event.id)
        self.assertEqual(event.category, "state_transition")
        self.assertEqual(event.severity, "info")
        self.assertEqual(event.summary, "Job moved from draft to confirmed.")
        self.assertEqual(event.user_id, self.env.user)
        self.assertEqual(event.company_id, self.env.company)
        self.assertEqual(event.related_model, "eh.log.adapter.profile")
        self.assertEqual(event.related_record_id, self.profile_test.id)
        payload = json.loads(event.context_json)
        self.assertEqual(payload["old_state"], "draft")
        self.assertEqual(payload["new_state"], "confirmed")

    def test_event_is_append_only(self):
        Event = self.env["eh.log.event"]
        event = Event.log(
            category="audit_note",
            summary="Initial note.",
        )
        with self.assertRaises(UserError) as ctx:
            event.summary = "Tampered summary"
        message = str(ctx.exception)
        self.assertIn("[EHL-EVENT-001]", message)
        self.assertIn("append-only", message)

    def test_event_company_ids_mirrors_company(self):
        Event = self.env["eh.log.event"]
        event = Event.log(
            category="audit_note",
            summary="Company isolation test.",
        )
        self.assertEqual(event.company_ids, event.company_id)

    def test_log_with_error_code(self):
        Event = self.env["eh.log.event"]
        event = Event.log(
            category="adapter_call",
            summary="Adapter call failed.",
            severity="error",
            error_code="EHL-ADAPTER-TIMEOUT-016",
        )
        self.assertEqual(event.error_code, "EHL-ADAPTER-TIMEOUT-016")
        self.assertEqual(event.severity, "error")
