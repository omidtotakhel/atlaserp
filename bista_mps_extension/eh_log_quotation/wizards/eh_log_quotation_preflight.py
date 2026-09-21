# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Preflight checklist wizard.

Aggregates every guard so the operator fixes everything in one pass
instead of confirming, hitting an error, fixing, confirming again,
hitting the next error, and so on. Each row carries a status, a
human-readable message, and a hint about the action that resolves it.
"""
from odoo import _, api, fields, models


CHECK_STATUS = [
    ("ok", "OK"),
    ("warning", "Warning"),
    ("blocked", "Blocked"),
    ("not_applicable", "Not Applicable"),
]


class EhLogQuotationPreflight(models.TransientModel):
    _name = "eh.log.quotation.preflight"
    _description = "Logistics Quotation Preflight Wizard"

    order_id = fields.Many2one(
        "sale.order",
        string="Quotation",
        required=True,
        ondelete="cascade",
    )

    overall_status = fields.Selection(
        selection=CHECK_STATUS,
        string="Overall",
        readonly=True,
    )

    line_ids = fields.One2many(
        "eh.log.quotation.preflight.line",
        "wizard_id",
        string="Checks",
        readonly=True,
    )

    summary = fields.Text(
        string="Summary",
        readonly=True,
    )

    def _run_checks(self):
        """Compose the checklist for the linked order."""
        self.ensure_one()
        order = self.order_id
        rows = []

        # Margin
        margin_status = order.eh_log_margin_status
        margin_message = _(
            "Gross margin %(pct).1f%% on revenue %(rev)s."
        ) % {
            "pct": order.eh_log_gross_margin_pct,
            "rev": order.eh_log_total_revenue_billable,
        }
        if margin_status == "above_warning":
            rows.append(("margin", "ok", margin_message,
                         _("No action needed.")))
        elif margin_status == "warning":
            rows.append(("margin", "warning", margin_message,
                         _("Below the warning threshold but above the "
                           "approval floor. Consider raising selected "
                           "charges or trimming costs.")))
        else:
            rows.append(("margin", "blocked", margin_message,
                         _("Margin below the approval floor. Manager "
                           "approval required before confirmation.")))

        # Credit
        credit_status = order.eh_log_credit_status
        if credit_status == "ok":
            rows.append(("credit", "ok",
                         order.eh_log_credit_message or _("Credit healthy."),
                         _("No action needed.")))
        elif credit_status == "warning":
            rows.append(("credit", "warning",
                         order.eh_log_credit_message,
                         _("Confirm with the credit controller before "
                           "promising delivery.")))
        else:
            rows.append(("credit", "blocked",
                         order.eh_log_credit_message,
                         _("Reduce the quote, request a credit "
                           "review, or take a security deposit.")))

        # KYC
        kyc_status = order.eh_log_kyc_status
        if kyc_status == "ok":
            rows.append(("kyc", "ok",
                         order.eh_log_kyc_message or _("KYC current."),
                         _("No action needed.")))
        elif kyc_status == "warning":
            rows.append(("kyc", "warning",
                         order.eh_log_kyc_message,
                         _("Refresh expiring documents.")))
        elif kyc_status == "expired":
            rows.append(("kyc", "blocked",
                         order.eh_log_kyc_message,
                         _("Upload current KYC documents before "
                           "confirming.")))
        else:
            rows.append(("kyc", "not_applicable",
                         order.eh_log_kyc_message or _("KYC not assessed."),
                         _("Install the Logistics KYC module to "
                           "enable structured KYC tracking.")))

        # Mode and direction
        if not order.eh_log_mode:
            rows.append(("mode", "blocked", _("Mode is not set."),
                         _("Pick the transport mode on the Logistics tab.")))
        else:
            rows.append(("mode", "ok",
                         _("Mode: %s") % dict(
                            order._fields["eh_log_mode"].selection
                         ).get(order.eh_log_mode), ""))
        if not order.eh_log_direction:
            rows.append(("direction", "blocked", _("Direction is not set."),
                         _("Pick import, export, or cross-trade.")))
        else:
            rows.append(("direction", "ok",
                         _("Direction: %s") % dict(
                            order._fields["eh_log_direction"].selection
                         ).get(order.eh_log_direction), ""))

        # Origin and destination
        if not order.eh_log_origin_country_id:
            rows.append(("origin", "warning",
                         _("Origin country is not set."),
                         _("Set the origin country on the Logistics tab.")))
        else:
            rows.append(("origin", "ok",
                         _("Origin: %s") % order.eh_log_origin_country_id.name, ""))
        if not order.eh_log_destination_country_id:
            rows.append(("destination", "warning",
                         _("Destination country is not set."),
                         _("Set the destination country on the Logistics tab.")))
        else:
            rows.append(("destination", "ok",
                         _("Destination: %s") % order.eh_log_destination_country_id.name, ""))

        # Incoterm (provided by sale_stock; absent in pure sale_management installs)
        incoterm = order.incoterm if "incoterm" in order._fields else False
        if not incoterm:
            rows.append(("incoterm", "warning",
                         _("Incoterm is not set."),
                         _("Pick an Incoterm under Other Information.")))
        else:
            rows.append(("incoterm", "ok",
                         _("Incoterm: %s") % incoterm.code, ""))

        # Charge codes on lines
        lines_without_code = [
            line for line in order.order_line
            if not line.display_type and not line.eh_log_charge_code_id
        ]
        if lines_without_code:
            rows.append(("charge_codes", "warning",
                         _("%d line(s) missing a charge code.") % len(lines_without_code),
                         _("Open each line and pick a charge code. "
                           "Apply Charge Template fills them in bulk.")))
        else:
            rows.append(("charge_codes", "ok",
                         _("Every line carries a charge code."), ""))

        # Cost on lines (Odoo's sale_margin purchase_price)
        lines_without_cost = [
            line for line in order.order_line
            if not line.display_type
            and not line.eh_log_is_disbursement
            and not line.purchase_price
        ]
        if lines_without_cost:
            rows.append(("purchase_price", "warning",
                         _("%d billable line(s) without a cost.") % len(lines_without_cost),
                         _("Enter the cost (Cost field) so the margin "
                           "guard works against realistic data.")))
        else:
            rows.append(("planned_cost", "ok",
                         _("Planned cost present on every billable line."), ""))

        # Approval
        if order.eh_log_requires_approval and not order.eh_log_approved_by_id:
            rows.append(("approval", "blocked",
                         _("Approval required and not yet stamped."),
                         _("A manager must use the Approve action.")))
        elif order.eh_log_requires_approval and order.eh_log_approved_by_id:
            rows.append(("approval", "ok",
                         _("Approved by %s.") % order.eh_log_approved_by_id.display_name, ""))
        else:
            rows.append(("approval", "not_applicable",
                         _("Approval not currently required."), ""))

        Line = self.env["eh.log.quotation.preflight.line"]
        Line.search([("wizard_id", "=", self.id)]).unlink()
        for sequence, (check, status, message, hint) in enumerate(rows, start=10):
            Line.create({
                "wizard_id": self.id,
                "sequence": sequence,
                "check": check,
                "status": status,
                "message": message,
                "hint": hint,
            })

        # Overall is the worst status across rows.
        worst_order = ["ok", "not_applicable", "warning", "blocked"]
        worst = "ok"
        for _check, status, *_rest in rows:
            if worst_order.index(status) > worst_order.index(worst):
                worst = status
        self.overall_status = worst

        if worst == "ok":
            self.summary = _(
                "All preflight checks passed. The order is ready to confirm."
            )
        elif worst == "warning":
            self.summary = _(
                "Some checks raised warnings. The order can be confirmed but "
                "review the warnings first."
            )
        else:
            self.summary = _(
                "One or more checks are blocking. Resolve every blocker "
                "before attempting to confirm."
            )

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}


class EhLogQuotationPreflightLine(models.TransientModel):
    _name = "eh.log.quotation.preflight.line"
    _description = "Logistics Quotation Preflight Line"
    _order = "wizard_id, sequence, id"

    wizard_id = fields.Many2one(
        "eh.log.quotation.preflight",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(default=10)

    check = fields.Char(string="Check", readonly=True)

    status = fields.Selection(
        selection=CHECK_STATUS,
        string="Status",
        readonly=True,
    )

    message = fields.Char(string="Message", readonly=True)

    hint = fields.Char(string="Suggested Action", readonly=True)
