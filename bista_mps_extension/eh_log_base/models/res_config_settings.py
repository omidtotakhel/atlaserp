# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Settings UI for the logistics suite.

Three sections under "ERP Heritage Logistics":

* General: default Incoterm, default mode, document expiry defaults.
* Approvals: margin warning and floor thresholds, credit warning
  percentage.
* Adapters: payload truncation limit, event retention windows.

Per-company fields are mirrored from res.company; system-wide
ir.config_parameter rows are exposed as Char and Integer fields with
explicit get_values / set_values overrides.
"""
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ----- Company-level (mirrored from res.company) -----

    eh_log_default_incoterm_id = fields.Many2one(
        related="company_id.eh_log_default_incoterm_id",
        readonly=False,
    )

    eh_log_default_mode = fields.Selection(
        related="company_id.eh_log_default_mode",
        readonly=False,
    )

    eh_log_margin_warning_threshold = fields.Float(
        related="company_id.eh_log_margin_warning_threshold",
        readonly=False,
    )

    eh_log_margin_floor_threshold = fields.Float(
        related="company_id.eh_log_margin_floor_threshold",
        readonly=False,
    )

    eh_log_kyc_warning_days = fields.Integer(
        related="company_id.eh_log_kyc_warning_days",
        readonly=False,
    )

    eh_log_credit_warning_pct = fields.Float(
        related="company_id.eh_log_credit_warning_pct",
        readonly=False,
    )

    # ----- System-wide (ir.config_parameter) -----

    eh_log_adapter_payload_max_chars = fields.Integer(
        string="Adapter Message Payload Max Chars",
        default=32768,
        help="Adapter messages are truncated above this size before "
             "storage to keep the database lean. Truncation happens "
             "after redaction.",
    )

    eh_log_event_retention_state_days = fields.Integer(
        string="Event Retention: State Transitions (days)",
        default=365,
    )

    eh_log_event_retention_adapter_days = fields.Integer(
        string="Event Retention: Adapter Calls (days)",
        default=180,
    )

    eh_log_event_retention_override_days = fields.Integer(
        string="Event Retention: Manual Overrides (days)",
        default=2555,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        res.update(
            eh_log_adapter_payload_max_chars=int(
                ICP.get_param(
                    "eh_log.base.adapter_message_payload_max_chars",
                    default="32768",
                )
            ),
            eh_log_event_retention_state_days=int(
                ICP.get_param(
                    "eh_log.base.event_retention_days.state_transition",
                    default="365",
                )
            ),
            eh_log_event_retention_adapter_days=int(
                ICP.get_param(
                    "eh_log.base.event_retention_days.adapter_call",
                    default="180",
                )
            ),
            eh_log_event_retention_override_days=int(
                ICP.get_param(
                    "eh_log.base.event_retention_days.override",
                    default="2555",
                )
            ),
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "eh_log.base.adapter_message_payload_max_chars",
            str(self.eh_log_adapter_payload_max_chars or 32768),
        )
        ICP.set_param(
            "eh_log.base.event_retention_days.state_transition",
            str(self.eh_log_event_retention_state_days or 365),
        )
        ICP.set_param(
            "eh_log.base.event_retention_days.adapter_call",
            str(self.eh_log_event_retention_adapter_days or 180),
        )
        ICP.set_param(
            "eh_log.base.event_retention_days.override",
            str(self.eh_log_event_retention_override_days or 2555),
        )
