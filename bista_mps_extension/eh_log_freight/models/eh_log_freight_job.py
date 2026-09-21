# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Freight forwarding job (the spine of the freight module).

Born from a confirmed sale order, advanced through a documented state
machine, carries milestones, parties, transport documents, and a live
cost-versus-revenue ledger that surfaces gross margin in the form
header.

Design notes:

* The job's analytic account is auto-created on first need so the
  cost ledger and the standard analytic reports work without operator
  setup.
* State transitions are gated. Direct writes to ``state`` are
  rejected; operators move the job via action methods that run a
  pre-flight check.
* Direct creation of a job from the menu is restricted to managers.
  The supported creation path is the sale order hook.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.eh_log_base.exceptions import JobStateConflictError

_logger = logging.getLogger(__name__)


JOB_STATES = [
    ("draft", "Draft"),
    ("booked", "Booked"),
    ("in_transit", "In Transit"),
    ("at_destination", "At Destination"),
    ("delivered", "Delivered"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]

# Allowed transitions: from -> set of valid to-states.
ALLOWED_TRANSITIONS = {
    "draft": {"booked", "cancelled"},
    "booked": {"in_transit", "cancelled"},
    "in_transit": {"at_destination", "cancelled"},
    "at_destination": {"delivered", "cancelled"},
    "delivered": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


class EhLogFreightJob(models.Model):
    _name = "eh.log.freight.job"
    _description = "Freight Forwarding Job"
    _inherit = ["mail.thread", "mail.activity.mixin", "eh.log.ux.mixin"]
    _order = "create_date desc, id desc"
    _rec_names_search = ["name", "customer_reference", "shipper_reference"]

    # ----- Identity -----

    name = fields.Char(
        string="Job Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )

    state = fields.Selection(
        selection=JOB_STATES,
        string="State",
        default="draft",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
        help=(
            "Lifecycle: Draft (created from quote) > Booked (carrier confirmed) > In Transit (departed) > At Destination (arrived) > Delivered (POD signed) > Closed (file finalised). State changes only via the action buttons; direct writes to this field are blocked."
        )
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_freight_job_company_rel",
        "job_id",
        "company_id",
        string="Companies",
        compute="_compute_company_ids",
        store=True,
        index=True,
        precompute=True,
    )

    # ----- Source linkage -----

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        ondelete="restrict",
        readonly=True,
        index=True,
        tracking=True,
        copy=False,
        help="Quotation the job was spawned from. Optional: operators "
             "also open jobs directly for shipments booked outside a "
             "quotation (agent nominations, inter-branch moves, ad-hoc "
             "bookings), so a job may legitimately have no sale order.",
    )

    sale_order_line_ids = fields.One2many(
        "sale.order.line",
        related="sale_order_id.order_line",
        readonly=True,
    )

    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        readonly=True,
        copy=False,
        help="Auto-created on demand. Cost lines and revenue lines "
             "tagged with this account roll up into the job's P and L.",
    )

    # ----- Lane -----

    mode = fields.Selection(
        selection=[
            ("sea", "Sea"),
            ("air", "Air"),
            ("road", "Road"),
            ("rail", "Rail"),
            ("multimodal", "Multimodal"),
            ("courier", "Courier or Express"),
        ],
        string="Mode",
        required=True,
        default="sea",
        index=True,
        tracking=True,
    )

    direction = fields.Selection(
        selection=[
            ("import", "Import"),
            ("export", "Export"),
            ("cross_trade", "Cross Trade"),
        ],
        string="Direction",
        required=True,
        default="import",
        index=True,
        tracking=True,
    )

    origin_country_id = fields.Many2one(
        "res.country",
        string="Origin Country",
        index=True,
        tracking=True,
    )

    destination_country_id = fields.Many2one(
        "res.country",
        string="Destination Country",
        index=True,
        tracking=True,
    )

    origin_location = fields.Char(string="Origin Location", tracking=True)

    destination_location = fields.Char(string="Destination Location", tracking=True)

    incoterm_id = fields.Many2one(
        "account.incoterms",
        string="Incoterm",
        tracking=True,
        help=(
            "Incoterm 2020 governing the cargo handover. Drives whose insurance covers the trip, who pays freight, and where the risk transfer occurs."
        )
    )

    # ----- Parties -----

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
        help="The party who placed the booking and is invoiced. "
             "Defaults from the sale order partner.",
    )

    shipper_id = fields.Many2one(
        "res.partner",
        string="Shipper",
        index=True,
        tracking=True,
        help="The party tendering the cargo at origin.",
    )

    consignee_id = fields.Many2one(
        "res.partner",
        string="Consignee",
        index=True,
        tracking=True,
        help="The party taking delivery at destination.",
    )

    notify_party_id = fields.Many2one(
        "res.partner",
        string="Notify Party",
        tracking=True,
        help=(
            "Optional. Third party to notify on arrival, typically the customs broker or warehouse operator. Goes onto the BL."
        )
    )

    customer_reference = fields.Char(string="Customer Reference", tracking=True)
    shipper_reference = fields.Char(string="Shipper Reference", tracking=True)

    # ----- Cargo summary -----

    cargo_description = fields.Text(string="Cargo Description")
    package_count = fields.Integer(string="Packages")
    gross_weight_kg = fields.Float(string="Gross Weight (kg)")
    volume_cbm = fields.Float(string="Volume (m3)")
    chargeable_weight_kg = fields.Float(string="Chargeable Weight (kg)")

    # ----- Dates -----

    booking_date = fields.Date(string="Booking Date", default=fields.Date.context_today, tracking=True)
    cutoff_date = fields.Datetime(string="Cutoff Date", tracking=True)
    etd_planned = fields.Datetime(string="Planned ETD", tracking=True)
    etd_actual = fields.Datetime(string="Actual ETD", tracking=True)
    eta_planned = fields.Datetime(string="Planned ETA", tracking=True)
    eta_actual = fields.Datetime(string="Actual ETA", tracking=True)
    delivered_at = fields.Datetime(string="Delivered At", readonly=True, copy=False, tracking=True)
    closed_at = fields.Datetime(string="Closed At", readonly=True, copy=False, tracking=True)

    # ----- Milestones -----

    milestone_ids = fields.One2many(
        "eh.log.freight.milestone",
        "job_id",
        string="Milestones",
        copy=False,
    )

    milestone_planned_count = fields.Integer(
        string="Planned Milestones",
        compute="_compute_milestone_counts",
        store=True,
    )

    milestone_actual_count = fields.Integer(
        string="Actual Milestones",
        compute="_compute_milestone_counts",
        store=True,
    )

    # ----- Margin (snapshot from the sale order at this layer) -----

    total_revenue = fields.Monetary(
        string="Revenue (Planned)",
        currency_field="currency_id",
        compute="_compute_margin_snapshot",
        store=True,
    )

    total_planned_cost = fields.Monetary(
        string="Planned Cost",
        currency_field="currency_id",
        compute="_compute_margin_snapshot",
        store=True,
    )

    gross_margin = fields.Monetary(
        string="Gross Margin (Planned)",
        currency_field="currency_id",
        compute="_compute_margin_snapshot",
        store=True,
    )

    gross_margin_pct = fields.Float(
        string="Gross Margin (%)",
        compute="_compute_margin_snapshot",
        store=True,
    )

    # ----- Actuals from the cost and revenue ledgers -----

    total_actual_cost = fields.Monetary(
        string="Actual Cost",
        currency_field="currency_id",
        compute="_compute_actuals",
        store=True,
        help="Sum of cost ledger lines (in company currency) excluding "
             "cancelled lines. Reflects committed and accrued and "
             "invoiced costs against the job.",
    )

    total_actual_revenue = fields.Monetary(
        string="Actual Revenue",
        currency_field="currency_id",
        compute="_compute_actuals",
        store=True,
        help="Sum of non-disbursement revenue ledger lines in company "
             "currency, excluding cancelled lines.",
    )

    actual_gross_margin = fields.Monetary(
        string="Actual Gross Margin",
        currency_field="currency_id",
        compute="_compute_actuals",
        store=True,
    )

    actual_gross_margin_pct = fields.Float(
        string="Actual Gross Margin (%)",
        compute="_compute_actuals",
        store=True,
    )

    margin_drift_pct = fields.Float(
        string="Margin Drift (pp)",
        compute="_compute_actuals",
        store=True,
        help="Actual margin percentage minus planned margin percentage "
             "expressed in percentage points. Negative drift means the "
             "job is performing worse than the original quotation; "
             "positive means better.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    # ----- Operational relations -----

    bl_ids = fields.One2many(
        "eh.log.freight.bl",
        "job_id",
        string="Bills of Lading",
    )

    bl_count = fields.Integer(
        string="Bills of Lading",
        compute="_compute_bl_count",
    )

    container_ids = fields.One2many(
        "eh.log.freight.container",
        "job_id",
        string="Containers",
    )

    container_count = fields.Integer(
        string="Containers",
        compute="_compute_container_count",
    )

    cost_line_ids = fields.One2many(
        "eh.log.freight.cost.line",
        "job_id",
        string="Cost Lines",
    )

    revenue_line_ids = fields.One2many(
        "eh.log.freight.revenue.line",
        "job_id",
        string="Revenue Lines",
    )

    # ----- Computes -----

    @api.depends("company_id")
    def _compute_company_ids(self):
        for job in self:
            job.company_ids = job.company_id

    @api.depends("milestone_ids", "milestone_ids.planned_at", "milestone_ids.actual_at")
    def _compute_milestone_counts(self):
        for job in self:
            job.milestone_planned_count = len(
                job.milestone_ids.filtered(lambda m: m.planned_at)
            )
            job.milestone_actual_count = len(
                job.milestone_ids.filtered(lambda m: m.actual_at)
            )

    @api.depends(
        "sale_order_id",
        "sale_order_id.eh_log_total_revenue_billable",
        "sale_order_id.eh_log_total_planned_cost",
        "sale_order_id.eh_log_gross_margin",
        "sale_order_id.eh_log_gross_margin_pct",
    )
    def _compute_margin_snapshot(self):
        for job in self:
            order = job.sale_order_id
            if not order:
                job.total_revenue = 0.0
                job.total_planned_cost = 0.0
                job.gross_margin = 0.0
                job.gross_margin_pct = 0.0
                continue
            job.total_revenue = order.eh_log_total_revenue_billable
            job.total_planned_cost = order.eh_log_total_planned_cost
            job.gross_margin = order.eh_log_gross_margin
            job.gross_margin_pct = order.eh_log_gross_margin_pct

    @api.depends(
        "cost_line_ids",
        "cost_line_ids.amount_company_currency",
        "cost_line_ids.state",
        "revenue_line_ids",
        "revenue_line_ids.amount_company_currency",
        "revenue_line_ids.state",
        "revenue_line_ids.is_disbursement",
        "gross_margin_pct",
    )
    def _compute_actuals(self):
        for job in self:
            actual_cost = sum(
                line.amount_company_currency
                for line in job.cost_line_ids
                if line.state != "cancelled"
            )
            actual_revenue = sum(
                line.amount_company_currency
                for line in job.revenue_line_ids
                if line.state != "cancelled" and not line.is_disbursement
            )
            margin = actual_revenue - actual_cost
            job.total_actual_cost = actual_cost
            job.total_actual_revenue = actual_revenue
            job.actual_gross_margin = margin
            if actual_revenue:
                actual_pct = (margin / actual_revenue) * 100.0
            else:
                actual_pct = 0.0
            job.actual_gross_margin_pct = actual_pct
            job.margin_drift_pct = actual_pct - job.gross_margin_pct

    @api.depends("bl_ids")
    def _compute_bl_count(self):
        for job in self:
            job.bl_count = len(job.bl_ids)

    @api.depends("container_ids")
    def _compute_container_count(self):
        for job in self:
            job.container_count = len(job.container_ids)

    # ----- Lifecycle -----

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                seq = self.env["ir.sequence"].next_by_code("eh.log.freight.job")
                vals["name"] = seq or _("New")
        jobs = super().create(vals_list)
        # Auto-seed the milestone timeline from required milestone types.
        for job in jobs:
            job._seed_milestones_for_mode()
            job._ensure_analytic_account()
        return jobs

    def _seed_milestones_for_mode(self):
        """Add required milestones for the job's mode if not already present."""
        self.ensure_one()
        Type = self.env["eh.log.freight.milestone.type"]
        types = Type.search([
            ("is_required", "=", True),
            "|",
                ("mode", "=", self.mode),
                ("mode", "=", "any"),
        ])
        existing_type_ids = self.milestone_ids.type_id.ids
        Milestone = self.env["eh.log.freight.milestone"]
        for milestone_type in types:
            if milestone_type.id in existing_type_ids:
                continue
            Milestone.create({
                "job_id": self.id,
                "type_id": milestone_type.id,
            })

    def _ensure_analytic_account(self):
        """Create the per-job analytic account on demand."""
        self.ensure_one()
        if self.analytic_account_id:
            return self.analytic_account_id
        Plan = self.env["account.analytic.plan"]
        plan = Plan.search([], limit=1)
        if not plan:
            plan = Plan.sudo().create({"name": _("ERP Heritage Logistics")})
        account = self.env["account.analytic.account"].sudo().create({
            "name": self.name,
            "plan_id": plan.id,
            "company_id": self.company_id.id,
            "partner_id": self.customer_id.id,
        })
        self.analytic_account_id = account
        return account

    # ----- State transitions -----

    def action_book(self):
        self._transition_state("booked")
        return True

    def action_set_in_transit(self):
        self._transition_state("in_transit")
        return True

    def action_set_at_destination(self):
        self._transition_state("at_destination")
        return True

    def action_set_delivered(self):
        self._transition_state("delivered")
        for job in self:
            job.delivered_at = fields.Datetime.now()
        return True

    def action_close(self):
        self._transition_state("closed")
        for job in self:
            job.closed_at = fields.Datetime.now()
        return True

    def action_cancel(self):
        self._transition_state("cancelled")
        return True

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
        }

    def action_view_milestones(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Milestones"),
            "res_model": "eh.log.freight.milestone",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
            "context": {"default_job_id": self.id},
        }

    def action_view_bls(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bills of Lading"),
            "res_model": "eh.log.freight.bl",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
            "context": {"default_job_id": self.id},
        }

    def action_view_containers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Containers"),
            "res_model": "eh.log.freight.container",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
            "context": {"default_job_id": self.id},
        }

    # ----- Write protection on state -----

    def write(self, vals):
        if "state" in vals and not self.env.context.get("eh_log_freight_internal_state_write"):
            raise UserError(_(
                "[EHL-JOB-STATE-002] State changes on a freight job must "
                "go through the action buttons (Book, Set In Transit, "
                "Deliver, Close, Cancel). Direct writes are rejected."
            ))
        return super().write(vals)

    def _transition_state(self, target_state: str):
        # Re-implement using the bypass flag.
        for job in self:
            current = job.state
            allowed = ALLOWED_TRANSITIONS.get(current, set())
            if target_state not in allowed:
                raise JobStateConflictError(
                    1,
                    _(
                        "Job %(name)s cannot move from %(current)s to "
                        "%(target)s. Allowed transitions from "
                        "%(current)s: %(allowed)s."
                    ) % {
                        "name": job.name,
                        "current": current,
                        "target": target_state,
                        "allowed": ", ".join(sorted(allowed)) or _("(none)"),
                    },
                )
            job.with_context(eh_log_freight_internal_state_write=True).write({
                "state": target_state,
            })
            self.env["eh.log.event"].log(
                category="state_transition",
                summary=_("Freight job %(name)s moved to %(state)s.") % {
                    "name": job.name, "state": target_state,
                },
                related_model="eh.log.freight.job",
                related_record_id=job.id,
                related_record_display=job.name,
                context={"from_state": current, "to_state": target_state},
            )
