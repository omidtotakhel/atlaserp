# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Adapter message log.

One row per request and response cycle. Stores enough to reproduce a
call (correlation id, idempotency key, sanitised payloads) plus enough
to understand outcomes (latency, retry count, status, error code,
linked originating record).

PII redaction is applied at write time per the profile's redaction
rules; the raw payload is never stored if redaction would leave PII
visible. The redaction layer uses a registered set of regexes plus a
JSON path list maintained per provider.

Retention is configurable via ir.config_parameter
``eh_log.base.adapter_message_retention_days`` (default 180). A daily
cron archives rows older than the threshold to a JSON file under the
filestore so the database stays lean while audit trails persist.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class EhLogAdapterMessage(models.Model):
    _name = "eh.log.adapter.message"
    _description = "Logistics Adapter Message Log"
    _order = "created_at desc, id desc"
    _rec_name = "correlation_id"

    # ----- Linkage -----

    profile_id = fields.Many2one(
        "eh.log.adapter.profile",
        string="Profile",
        required=True,
        ondelete="restrict",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        related="profile_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_adapter_message_company_rel",
        "message_id",
        "company_id",
        string="Companies",
        compute="_compute_company_ids",
        store=True,
        index=True,
        precompute=True,
    )

    related_model = fields.Char(
        string="Related Model",
        index=True,
        help="Odoo model name that originated this call, e.g. "
             "'eh.log.customs.declaration'. Lets the UI link back from "
             "the message log to the operational record.",
    )

    related_record_id = fields.Integer(
        string="Related Record ID",
        index=True,
        help="Database id of the originating record. Pair with "
             "related_model for the back link.",
    )

    related_record_display = fields.Char(
        string="Related Record",
        help="Human-readable reference (e.g. customs declaration "
             "number) snapshotted at write time so the log entry is "
             "readable even after the originating record is archived.",
    )

    # ----- Identity -----

    correlation_id = fields.Char(
        string="Correlation ID",
        required=True,
        index=True,
        help="Unique per-call identifier propagated to the provider "
             "for traceability. Generated client-side as a UUID4.",
    )

    idempotency_key = fields.Char(
        string="Idempotency Key",
        index=True,
        help="Optional caller-supplied key the provider uses to "
             "deduplicate retried requests. Empty when the call is "
             "naturally idempotent (e.g. a status query).",
    )

    message_type = fields.Char(
        string="Message Type",
        required=True,
        index=True,
        help="Adapter-defined message label, e.g. 'declaration_submit', "
             "'health_check', 'status_query'.",
    )

    # ----- Cycle -----

    direction = fields.Selection(
        selection=[
            ("outbound", "Outbound"),
            ("inbound", "Inbound"),
        ],
        string="Direction",
        required=True,
        default="outbound",
        index=True,
    )

    status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("retry", "Retried"),
            ("failure", "Failure"),
            ("timeout", "Timed Out"),
            ("rejected", "Rejected by Provider"),
            ("dead_letter", "Dead Letter"),
        ],
        string="Status",
        required=True,
        default="pending",
        index=True,
    )

    retry_count = fields.Integer(string="Retry Count", default=0)

    latency_ms = fields.Integer(string="Latency (ms)")

    http_status = fields.Integer(string="HTTP Status")

    error_code = fields.Char(
        string="Error Code",
        help="Provider-returned error code, surfaced verbatim. The "
             "human message is in the body; this field is for grep.",
    )

    error_message = fields.Text(string="Error Message")

    # ----- Payload (redacted at write time) -----

    request_payload = fields.Text(
        string="Request Payload",
        help="Sanitised request payload. Original PII redacted per "
             "the profile's redaction rules. Truncated above the size "
             "limit set by ir.config_parameter "
             "eh_log.base.adapter_message_payload_max_chars.",
    )

    response_payload = fields.Text(
        string="Response Payload",
        help="Sanitised response payload. Same redaction and truncation "
             "rules as the request payload.",
    )

    request_headers = fields.Text(
        string="Request Headers (sanitised)",
        help="Authentication headers redacted before storage; "
             "Content-Type, Accept, and other operational headers retained.",
    )

    response_headers = fields.Text(
        string="Response Headers",
    )

    # ----- Timestamps -----

    created_at = fields.Datetime(
        string="Created",
        default=fields.Datetime.now,
        required=True,
        index=True,
        readonly=True,
    )

    completed_at = fields.Datetime(
        string="Completed",
        readonly=True,
    )

    # ----- Computes -----

    @api.depends("profile_id", "profile_id.company_id")
    def _compute_company_ids(self):
        for message in self:
            message.company_ids = message.profile_id.company_id

    # ----- Actions -----

    def action_open_related_record(self):
        """Open the originating record in its native form view."""
        self.ensure_one()
        if not self.related_model or not self.related_record_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Originating Record"),
            "res_model": self.related_model,
            "view_mode": "form",
            "res_id": self.related_record_id,
        }

    def action_replay(self):
        """Re-dispatch this outbound message via its adapter.

        Useful from the dead-letter queue or after a credential fix.
        Concrete adapters opt into replay support by overriding
        ``replay_from_message`` on the registered class. Adapters that
        cannot safely replay (e.g. one-shot mutations without server
        idempotency) return False and the action surfaces a clear
        message to the operator.
        """
        from .. import adapter_registry
        replayed = self.env["eh.log.adapter.message"]
        for message in self:
            if message.direction != "outbound":
                continue
            adapter_cls = adapter_registry.get(message.profile_id.provider_code)
            if not adapter_cls:
                continue
            adapter = adapter_cls(message.profile_id)
            new_message = adapter.replay_from_message(message)
            if new_message:
                replayed += new_message
        if replayed:
            return {
                "type": "ir.actions.act_window",
                "name": _("Replayed Messages"),
                "res_model": "eh.log.adapter.message",
                "view_mode": "list,form",
                "domain": [("id", "in", replayed.ids)],
            }
        return False
