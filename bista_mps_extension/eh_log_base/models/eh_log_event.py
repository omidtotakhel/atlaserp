# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Operational audit log.

Captures every state transition, override action, and significant
adapter outcome with structured context. The model is append-only at
the API level: writes after creation are restricted to the technical
``unlink`` path used by the retention cron.

Why a dedicated event log on top of mail.thread chatter:

* Chatter is per-record and per-user-readable; it is not a structured
  audit feed across the suite.
* Compliance reviews need to query "every override of a credit limit
  in Q2" or "every adapter timeout against Mirsal in March" without
  joining across every operational table's chatter.
* Retention is per-event-category here, not per-record.

Categories are extensible: per-vertical modules append to the
``eh.log.event.category`` selection via ``selection_add`` so the base
keeps a small starter set and the customs / freight / transport
modules add their own.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EhLogEvent(models.Model):
    _name = "eh.log.event"
    _description = "Logistics Operational Event"
    _order = "occurred_at desc, id desc"
    _rec_name = "summary"

    # ----- Identity and time -----

    occurred_at = fields.Datetime(
        string="Occurred At",
        required=True,
        default=fields.Datetime.now,
        index=True,
        readonly=True,
    )

    category = fields.Selection(
        selection=[
            ("state_transition", "State Transition"),
            ("override", "Manual Override"),
            ("adapter_call", "Adapter Call"),
            ("config_change", "Configuration Change"),
            ("approval", "Approval Decision"),
            ("audit_note", "Audit Note"),
        ],
        string="Category",
        required=True,
        index=True,
        readonly=True,
    )

    severity = fields.Selection(
        selection=[
            ("info", "Info"),
            ("notice", "Notice"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        string="Severity",
        required=True,
        default="info",
        index=True,
        readonly=True,
    )

    summary = fields.Char(
        string="Summary",
        required=True,
        readonly=True,
        help="One-line human-readable description of the event. The "
             "structured payload sits in the context_json field.",
    )

    # ----- Linkage -----

    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        index=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        readonly=True,
    )

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_event_company_rel",
        "event_id",
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
        readonly=True,
    )

    related_record_id = fields.Integer(
        string="Related Record ID",
        index=True,
        readonly=True,
    )

    related_record_display = fields.Char(
        string="Related Record",
        readonly=True,
    )

    # ----- Payload -----

    context_json = fields.Text(
        string="Context (JSON)",
        readonly=True,
        help="Structured payload serialised as JSON. Audit reviewers "
             "search this field for specific keys and values.",
    )

    error_code = fields.Char(
        string="Error Code",
        index=True,
        readonly=True,
    )

    # ----- Computes -----

    @api.depends("company_id")
    def _compute_company_ids(self):
        for event in self:
            event.company_ids = event.company_id

    # ----- Write protection -----

    def write(self, vals):
        # Allow updates only to non-data fields used by the retention cron.
        forbidden = set(vals) - {
            "active",
        }
        if forbidden:
            raise UserError(_(
                "[EHL-EVENT-001] Operational events are append-only. "
                "Editing the following fields is not permitted: %(fields)s."
            ) % {"fields": ", ".join(sorted(forbidden))})
        return super().write(vals)

    @api.model
    def log(
        self,
        category: str,
        summary: str,
        severity: str = "info",
        related_model: str = None,
        related_record_id: int = None,
        related_record_display: str = None,
        context: dict = None,
        error_code: str = None,
    ):
        """Create an event row from any model with one call.

        Use this from compute methods, state transitions, override
        actions, and adapter wrappers. The signature is intentionally
        permissive so callers do not need to construct a dict.
        """
        import json
        return self.sudo().create({
            "category": category,
            "severity": severity,
            "summary": summary,
            "related_model": related_model or False,
            "related_record_id": related_record_id or 0,
            "related_record_display": related_record_display or False,
            "context_json": json.dumps(context, default=str) if context else False,
            "error_code": error_code or False,
        })

    # ----- Retention -----

    @api.model
    def _gc_old_events(self):
        """Cron entry point: remove events older than the retention window.

        The retention window is per-category to allow compliance
        evidence (overrides, approvals) to outlive operational chatter
        (state transitions, adapter calls).
        """
        ICP = self.env["ir.config_parameter"].sudo()
        defaults = {
            "state_transition": 365,
            "override": 2555,            # 7 years
            "adapter_call": 180,
            "config_change": 2555,
            "approval": 2555,
            "audit_note": 365,
        }
        for category, default_days in defaults.items():
            param_key = f"eh_log.base.event_retention_days.{category}"
            days = int(ICP.get_param(param_key, default=default_days))
            if days <= 0:
                continue
            cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
            stale = self.sudo().search([
                ("category", "=", category),
                ("occurred_at", "<", cutoff),
            ])
            if stale:
                _logger.info(
                    "eh.log.event GC: pruning %d %s events older than "
                    "%d days.", len(stale), category, days,
                )
                # Bypass write protection by using the underlying ORM unlink.
                stale.sudo().unlink()
