# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Sale order extension for logistics.

Adds the logistics-specific fields, the live margin and credit and
KYC guards, and the approval flow. Confirmation hooks check the
guards and raise typed exceptions on hard failures.
"""
import logging

from odoo import _, api, fields, models

from odoo.addons.eh_log_base.exceptions import (
    CreditExposureError,
    KYCExpiredError,
    UserError,
)

_logger = logging.getLogger(__name__)


MARGIN_STATUS = [
    ("above_warning", "Healthy"),
    ("warning", "Warning"),
    ("below_floor", "Below Floor"),
]

CREDIT_STATUS = [
    ("ok", "Healthy"),
    ("warning", "Warning"),
    ("blocked", "Blocked"),
]

KYC_STATUS = [
    ("ok", "Healthy"),
    ("warning", "Warning"),
    ("expired", "Expired"),
    ("not_assessed", "Not Assessed"),
]


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "eh.log.ux.mixin"]

    # ----- Logistics scope flag -----

    eh_log_is_logistics = fields.Boolean(
        string="Logistics Quotation",
        default=False,
        index=True,
        tracking=True,
        help="Marks this sale order as a logistics quotation. The "
             "logistics tab, guards, and downstream job creation hooks "
             "only fire when this is set. Auto-set when a charge "
             "template is applied or a logistics charge code is used "
             "on any line.",
    )

    # ----- Lane and mode -----

    eh_log_mode = fields.Selection(
        selection=[
            ("sea", "Sea"),
            ("air", "Air"),
            ("road", "Road"),
            ("rail", "Rail"),
            ("multimodal", "Multimodal"),
            ("courier", "Courier or Express"),
        ],
        string="Mode",
        index=True,
        tracking=True,
    )

    eh_log_direction = fields.Selection(
        selection=[
            ("import", "Import"),
            ("export", "Export"),
            ("cross_trade", "Cross Trade"),
        ],
        string="Direction",
        index=True,
        tracking=True,
    )

    eh_log_origin_country_id = fields.Many2one(
        "res.country",
        string="Origin Country",
        index=True,
        tracking=True,
    )

    eh_log_destination_country_id = fields.Many2one(
        "res.country",
        string="Destination Country",
        index=True,
        tracking=True,
    )

    eh_log_origin_location = fields.Char(
        string="Origin Location",
        help="Specific port, airport, or pickup point. Free text at "
             "this layer; the freight forwarding module replaces with "
             "structured port and airport master data.",
    )

    eh_log_destination_location = fields.Char(
        string="Destination Location",
        help="Specific port, airport, or delivery point.",
    )

    eh_log_charge_template_id = fields.Many2one(
        "eh.log.charge.template",
        string="Last Applied Template",
        readonly=True,
        copy=False,
        help=(
            "Lane template to apply. Selecting one populates the order lines with the template's charge codes, default quantities, and unit prices."
        )
    )

    # ----- Margin -----

    eh_log_total_planned_cost = fields.Monetary(
        string="Total Planned Cost",
        currency_field="currency_id",
        compute="_compute_eh_log_margin",
        store=True,
        help="Sum of planned cost across non-disbursement lines.",
    )

    eh_log_total_revenue_billable = fields.Monetary(
        string="Billable Revenue",
        currency_field="currency_id",
        compute="_compute_eh_log_margin",
        store=True,
        help="Sum of revenue across non-disbursement lines. "
             "Disbursements are excluded from margin computation.",
    )

    eh_log_gross_margin = fields.Monetary(
        string="Gross Margin",
        currency_field="currency_id",
        compute="_compute_eh_log_margin",
        store=True,
    )

    eh_log_gross_margin_pct = fields.Float(
        string="Gross Margin (%)",
        compute="_compute_eh_log_margin",
        store=True,
        help="Margin / billable revenue, expressed as a percentage. "
             "Zero when there is no billable revenue.",
    )

    eh_log_margin_status = fields.Selection(
        selection=MARGIN_STATUS,
        string="Margin Status",
        compute="_compute_eh_log_margin",
        store=True,
        index=True,
        help=(
            "Live margin status: above target (green), within tolerance (amber), below threshold (red). Red orders require manager approval to confirm."
        )
    )

    # ----- Credit -----

    eh_log_credit_exposure = fields.Monetary(
        string="Customer Exposure",
        currency_field="currency_id",
        compute="_compute_eh_log_credit",
        store=False,
        help="Sum of the partner's currently outstanding receivables "
             "in the company currency. Recomputed on every read.",
    )

    eh_log_credit_status = fields.Selection(
        selection=CREDIT_STATUS,
        string="Credit Status",
        compute="_compute_eh_log_credit",
        store=False,
        index=False,
        help=(
            "Live customer credit status: green (OK), amber (within tolerance), red (over limit). Confirming a red order requires manager approval."
        )
    )

    eh_log_credit_message = fields.Char(
        string="Credit Message",
        compute="_compute_eh_log_credit",
        store=False,
    )

    # ----- KYC -----

    eh_log_kyc_status = fields.Selection(
        selection=KYC_STATUS,
        string="KYC Status",
        compute="_compute_eh_log_kyc",
        store=False,
        help=(
            "Customer KYC status: green (current), amber (renewal due), red (expired or missing). Red blocks confirmation."
        )
    )

    eh_log_kyc_message = fields.Char(
        string="KYC Message",
        compute="_compute_eh_log_kyc",
        store=False,
    )

    # ----- Approval -----

    eh_log_requires_approval = fields.Boolean(
        string="Requires Approval",
        compute="_compute_eh_log_requires_approval",
        store=True,
        help="Computed from margin status and any other configured "
             "trigger. When True, confirmation is gated until a "
             "manager approves.",
    )

    eh_log_approval_reasons = fields.Text(
        string="Approval Reasons",
        compute="_compute_eh_log_requires_approval",
        store=True,
        help="One reason per line, surfaced on the form so the "
             "manager sees what they are approving.",
    )

    eh_log_approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        copy=False,
        tracking=True,
    )

    eh_log_approved_at = fields.Datetime(
        string="Approved At",
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ----- Computes -----

    @api.depends(
        "order_line",
        "order_line.product_uom_qty",
        "order_line.price_subtotal",
        "order_line.purchase_price",
        "order_line.eh_log_charge_code_id.is_disbursement",
        "company_id.eh_log_margin_warning_threshold",
        "company_id.eh_log_margin_floor_threshold",
    )
    def _compute_eh_log_margin(self):
        # Cost source is the standard sale_margin purchase_price field
        # so we do not duplicate Odoo's own cost concept. Disbursement
        # lines are still excluded from margin per the suite contract.
        for order in self:
            cost_total = 0.0
            revenue_total = 0.0
            for line in order.order_line:
                if line.display_type:
                    continue
                if (
                    line.eh_log_charge_code_id
                    and line.eh_log_charge_code_id.is_disbursement
                ):
                    continue
                cost_total += line.purchase_price * line.product_uom_qty
                revenue_total += line.price_subtotal
            margin = revenue_total - cost_total
            order.eh_log_total_planned_cost = cost_total
            order.eh_log_total_revenue_billable = revenue_total
            order.eh_log_gross_margin = margin
            if revenue_total:
                pct = (margin / revenue_total) * 100.0
            else:
                pct = 0.0
            order.eh_log_gross_margin_pct = pct
            warn = order.company_id.eh_log_margin_warning_threshold
            floor = order.company_id.eh_log_margin_floor_threshold
            if pct >= warn:
                order.eh_log_margin_status = "above_warning"
            elif pct >= floor:
                order.eh_log_margin_status = "warning"
            else:
                order.eh_log_margin_status = "below_floor"

    @api.depends_context("uid")
    @api.depends("partner_id", "amount_total", "currency_id")
    def _compute_eh_log_credit(self):
        for order in self:
            partner = order.partner_id
            if not partner:
                order.eh_log_credit_exposure = 0.0
                order.eh_log_credit_status = "ok"
                order.eh_log_credit_message = False
                continue
            exposure = order._eh_log_compute_partner_exposure()
            limit = order._eh_log_resolve_credit_limit()
            warn_pct = order.company_id.eh_log_credit_warning_pct or 0.0
            order.eh_log_credit_exposure = exposure
            if not limit:
                order.eh_log_credit_status = "ok"
                order.eh_log_credit_message = _(
                    "No credit limit set on this customer."
                )
                continue
            ratio = (exposure / limit) * 100.0 if limit else 0.0
            if ratio >= 100.0:  # noqa: gcclog-hardcode 100% of approved credit limit is the contract definition of "limit"
                order.eh_log_credit_status = "blocked"
                order.eh_log_credit_message = _(
                    "Exposure %(ratio).1f%% of approved limit."
                ) % {"ratio": ratio}
            elif ratio >= warn_pct:
                order.eh_log_credit_status = "warning"
                order.eh_log_credit_message = _(
                    "Exposure %(ratio).1f%% of approved limit "
                    "(warning at %(warn).1f%%)."
                ) % {"ratio": ratio, "warn": warn_pct}
            else:
                order.eh_log_credit_status = "ok"
                order.eh_log_credit_message = _(
                    "Exposure %(ratio).1f%% of approved limit."
                ) % {"ratio": ratio}

    def _eh_log_compute_partner_exposure(self) -> float:
        """Sum of the partner's currently due receivables in company currency.

        Read from posted, unreconciled receivable journal items. The
        accounting module is a hard dependency of this module so the
        join is always safe.
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return 0.0
        AccountMoveLine = self.env["account.move.line"].sudo()
        receivables = AccountMoveLine.search([
            ("partner_id", "=", partner.id),
            ("account_id.account_type", "=", "asset_receivable"),
            ("parent_state", "=", "posted"),
            ("reconciled", "=", False),
            ("company_id", "=", self.company_id.id),
        ])
        # amount_residual is signed; receivables are positive when due.
        return sum(receivables.mapped("amount_residual"))

    def _eh_log_resolve_credit_limit(self) -> float:
        """Pull the customer's approved credit limit.

        Uses the standard ``res.partner.credit_limit`` field shipped
        by ``account``. If a richer credit module is installed
        downstream (e.g. eh_account_credit_limit), this method is the
        place a subclass overrides to pick up the additional state.
        """
        self.ensure_one()
        partner = self.partner_id
        return partner.credit_limit if partner else 0.0

    @api.depends_context("uid")
    @api.depends("partner_id", "company_id")
    def _compute_eh_log_kyc(self):
        # Base implementation is conservative: returns 'not_assessed'
        # when the dedicated KYC module (eh_log_kyc, future) is not
        # installed. Subclassed there to read real KYC document state.
        for order in self:
            if not order.partner_id:
                order.eh_log_kyc_status = "not_assessed"
                order.eh_log_kyc_message = False
                continue
            order.eh_log_kyc_status = "not_assessed"
            order.eh_log_kyc_message = _(
                "KYC not assessed. Install the Logistics KYC module to "
                "track document expiry against this customer."
            )

    @api.depends(
        "eh_log_margin_status",
        "eh_log_credit_status",
        "eh_log_kyc_status",
    )
    def _compute_eh_log_requires_approval(self):
        for order in self:
            reasons = []
            if order.eh_log_margin_status == "below_floor":
                reasons.append(_(
                    "Margin %(pct).1f%% is below the company floor "
                    "of %(floor).1f%%."
                ) % {
                    "pct": order.eh_log_gross_margin_pct,
                    "floor": order.company_id.eh_log_margin_floor_threshold,
                })
            if order.eh_log_credit_status == "warning":
                reasons.append(_(
                    "Customer credit exposure is in the warning band."
                ))
            if order.eh_log_kyc_status == "expired":
                reasons.append(_(
                    "Customer KYC is expired."
                ))
            order.eh_log_requires_approval = bool(reasons)
            order.eh_log_approval_reasons = "\n".join(reasons) if reasons else False

    # ----- Public actions -----

    def action_eh_log_run_preflight(self):
        """Open the preflight wizard for this order."""
        self.ensure_one()
        wizard = self.env["eh.log.quotation.preflight"].create({
            "order_id": self.id,
        })
        wizard._run_checks()
        return {
            "type": "ir.actions.act_window",
            "name": _("Preflight Checklist"),
            "res_model": "eh.log.quotation.preflight",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_eh_log_apply_template(self):
        """Open the apply-template wizard."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Apply Charge Template"),
            "res_model": "eh.log.charge.template.apply",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def action_eh_log_approve(self):
        """Manager approval action.

        Stamps the approver and timestamp, writes a chatter entry, and
        creates an eh.log.event row in the approval category.
        """
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(
            "eh_log_base.group_eh_log_manager"
        ):
            raise UserError(_(
                "[EHL-APPROVAL-001] Only logistics managers can approve "
                "this quotation. Ask your manager to take action."
            ))
        if not self.eh_log_requires_approval:
            raise UserError(_(
                "[EHL-APPROVAL-002] This quotation does not currently "
                "require approval. The Approve action is only available "
                "when the margin, credit, or KYC guard surfaces a "
                "blocking reason."
            ))
        self.write({
            "eh_log_approved_by_id": self.env.user.id,
            "eh_log_approved_at": fields.Datetime.now(),
        })
        body = _(
            "Quotation approved by %(user)s. Reasons recorded at "
            "approval time:\n%(reasons)s"
        ) % {
            "user": self.env.user.display_name,
            "reasons": self.eh_log_approval_reasons or _("(none)"),
        }
        self.message_post(body=body)
        self.env["eh.log.event"].log(
            category="approval",
            severity="notice",
            summary=_("Logistics quotation %s approved.") % self.name,
            related_model="sale.order",
            related_record_id=self.id,
            related_record_display=self.name,
            context={
                "approver_id": self.env.user.id,
                "approver_login": self.env.user.login,
                "reasons": self.eh_log_approval_reasons,
                "margin_pct": self.eh_log_gross_margin_pct,
                "credit_status": self.eh_log_credit_status,
            },
        )
        return True

    # ----- Confirmation hook -----

    def action_confirm(self):
        """Run hard guards before delegating to the standard confirm.

        Soft warnings (warning-band margin, warning-band credit, KYC
        expiry within the warning window) are surfaced by the
        preflight checklist; this method only blocks on truly
        blocking states (credit blocked, KYC expired hard, approval
        required without an approver).
        """
        for order in self:
            if not order.eh_log_is_logistics:
                continue
            if order.eh_log_credit_status == "blocked":
                raise CreditExposureError(
                    1,
                    _(
                        "Cannot confirm %(name)s for %(partner)s. "
                        "Outstanding exposure of %(exposure)s exceeds "
                        "the approved credit limit. Reduce the "
                        "quotation, request credit limit review, or "
                        "take a security deposit."
                    ) % {
                        "name": order.name,
                        "partner": order.partner_id.display_name,
                        "exposure": order.eh_log_credit_exposure,
                    },
                )
            if order.eh_log_kyc_status == "expired":
                raise KYCExpiredError(
                    1,
                    _(
                        "Cannot confirm %(name)s. Customer KYC for "
                        "%(partner)s has expired documents. Refresh "
                        "the KYC documents or override with manager "
                        "approval first."
                    ) % {
                        "name": order.name,
                        "partner": order.partner_id.display_name,
                    },
                )
            if order.eh_log_requires_approval and not order.eh_log_approved_by_id:
                raise UserError(_(
                    "[EHL-APPROVAL-003] Quotation %(name)s requires "
                    "manager approval before confirmation. Reasons:\n"
                    "%(reasons)s\n\nUse the Approve action to record "
                    "the decision, then confirm again."
                ) % {
                    "name": order.name,
                    "reasons": order.eh_log_approval_reasons or _("(none)"),
                })
        return super().action_confirm()

    # ----- Onchange UI assistance -----

    @api.onchange("eh_log_charge_template_id")
    def _onchange_eh_log_charge_template_id(self):
        # Set the mode on the order from the template's mode hint.
        if self.eh_log_charge_template_id and self.eh_log_charge_template_id.mode != "any":
            self.eh_log_mode = self.eh_log_charge_template_id.mode
        if self.eh_log_charge_template_id and self.eh_log_charge_template_id.direction != "any":
            self.eh_log_direction = self.eh_log_charge_template_id.direction

    # ------------------------------------------------------------------
    # Smart-form onchanges (UX intelligence)
    # ------------------------------------------------------------------
    @api.onchange("partner_id")
    def _onchange_partner_id_logistics(self):
        """When the customer changes, surface credit / KYC posture
        as a non-blocking warning the operator sees immediately.
        Also auto-set the logistics flag if the customer has logistics
        history (any prior eh_log_is_logistics order).
        """
        if not self.partner_id:
            return
        SO = self.env["sale.order"]
        prior = SO.search_count([
            ("partner_id", "=", self.partner_id.id),
            ("eh_log_is_logistics", "=", True),
        ])
        if prior:
            self.eh_log_is_logistics = True
        # Surface credit / KYC posture early.
        if self.eh_log_credit_status == "blocked":
            return {
                "warning": {
                    "title": _("Customer credit blocked"),
                    "message": self.eh_log_credit_message or _(
                        "Outstanding exposure exceeds the approved limit."
                    ),
                },
            }
        if self.eh_log_kyc_status == "expired":
            return {
                "warning": {
                    "title": _("Customer KYC expired"),
                    "message": self.eh_log_kyc_message or _(
                        "Customer KYC documents have expired; refresh "
                        "before confirming."
                    ),
                },
            }

    @api.onchange("eh_log_mode")
    def _onchange_eh_log_mode(self):
        """When the operator picks a transport mode, set the
        is_logistics flag and clear lane fields that no longer apply.
        """
        if self.eh_log_mode:
            self.eh_log_is_logistics = True
        # Air mode cannot be cross-trade by definition: charterer is
        # always one of origin/destination; flag this for the operator.
        if self.eh_log_mode == "air" and self.eh_log_direction == "cross_trade":
            return {
                "warning": {
                    "title": _("Cross-trade air"),
                    "message": _(
                        "Cross-trade air bookings require a forwarder "
                        "presence in both origin and destination "
                        "countries; verify before quoting."
                    ),
                },
            }

    @api.onchange("eh_log_direction")
    def _onchange_eh_log_direction(self):
        """Direction picked: pre-fill the country pair from the
        company's address as the default origin (export) or
        destination (import).
        """
        if not self.eh_log_direction:
            return
        company_country = self.company_id.country_id
        if not company_country:
            return
        if self.eh_log_direction == "export" and not self.eh_log_origin_country_id:
            self.eh_log_origin_country_id = company_country
        if self.eh_log_direction == "import" and not self.eh_log_destination_country_id:
            self.eh_log_destination_country_id = company_country

    @api.onchange("eh_log_origin_country_id", "eh_log_destination_country_id")
    def _onchange_eh_log_lane(self):
        """Same-country lane is unusual: nudge the operator."""
        if (
            self.eh_log_origin_country_id
            and self.eh_log_destination_country_id
            and self.eh_log_origin_country_id == self.eh_log_destination_country_id
            and self.eh_log_direction != "cross_trade"
        ):
            return {
                "warning": {
                    "title": _("Domestic lane detected"),
                    "message": _(
                        "Origin and destination countries match. "
                        "Switch direction to Cross Trade if this is "
                        "intentional, otherwise re-check the lane."
                    ),
                },
            }

    @api.onchange("eh_log_is_logistics")
    def _onchange_eh_log_is_logistics(self):
        """Switching the logistics flag off when the order has
        logistics charge codes is dangerous; surface a warning.
        """
        if not self.eh_log_is_logistics:
            has_logistics_lines = any(
                line.eh_log_charge_code_id for line in self.order_line
            )
            if has_logistics_lines:
                return {
                    "warning": {
                        "title": _("Logistics lines present"),
                        "message": _(
                            "This quotation has logistics charge codes "
                            "on its lines. Disabling the logistics "
                            "flag will skip the credit / KYC / margin "
                            "guards on confirmation."
                        ),
                    },
                }

    # ------------------------------------------------------------------
    # Action methods returning toasts (UX feedback)
    # ------------------------------------------------------------------
    def action_eh_log_approve_with_toast(self):
        self.ensure_one()
        self.action_eh_log_approve()
        return self._notify_success(
            title=_("Quotation approved"),
            message=_(
                "%(name)s approved. You can now confirm the quotation."
            ) % {"name": self.name},
        )

    def action_eh_log_run_preflight_with_toast(self):
        self.ensure_one()
        action = self.action_eh_log_run_preflight()
        return action

    # ------------------------------------------------------------------
    # Activity scheduling (workflow nudges)
    # ------------------------------------------------------------------
    def _schedule_approval_nudge(self):
        for order in self:
            if not order.eh_log_requires_approval or order.eh_log_approved_by_id:
                continue
            order._nudge(
                summary=_("Quotation %s requires manager approval") % order.name,
                note=order.eh_log_approval_reasons or "",
            )
