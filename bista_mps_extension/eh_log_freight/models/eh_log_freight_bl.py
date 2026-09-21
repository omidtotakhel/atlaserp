# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Bill of lading: HBL, MBL, HAWB, MAWB on one model.

Why one model with a bl_type variant rather than four:

* The data shape is 90% common (number, date, parties, carrier,
  vessel or flight, ports, terms).
* Reports, EDI mapping, and customs declaration linkage all key on
  the same field set.
* The remaining 10% (vessel and voyage for sea, flight for air) is
  exposed conditionally in the form via invisible= and select-
  applicable masters.

State machine:

    draft -> issued -> released -> closed

Voiding (rare, document-level mistake) jumps draft to cancelled or
issued to cancelled with a reason on the chatter.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.eh_log_base.exceptions import JobStateConflictError

_logger = logging.getLogger(__name__)


BL_STATES = [
    ("draft", "Draft"),
    ("issued", "Issued"),
    ("released", "Released"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]

BL_TYPES = [
    ("hbl", "House Bill of Lading"),
    ("mbl", "Master Bill of Lading"),
    ("hawb", "House Air Waybill"),
    ("mawb", "Master Air Waybill"),
]

ALLOWED_BL_TRANSITIONS = {
    "draft": {"issued", "cancelled"},
    "issued": {"released", "cancelled"},
    "released": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


class EhLogFreightBl(models.Model):
    _name = "eh.log.freight.bl"
    _description = "Freight Bill of Lading"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, id desc"
    _rec_names_search = ["number", "name"]

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )

    job_id = fields.Many2one(
        "eh.log.freight.job",
        string="Job",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )

    bl_type = fields.Selection(
        selection=BL_TYPES,
        string="Document Type",
        required=True,
        index=True,
        tracking=True,
    )

    state = fields.Selection(
        selection=BL_STATES,
        string="State",
        default="draft",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )

    # ----- Document number and dates -----

    number = fields.Char(
        string="BL Number",
        index=True,
        tracking=True,
        help="Carrier-issued bill of lading number (e.g. "
             "MAEU1234567 for sea, 020-12345678 for air). Captured on "
             "issue.",
    )

    issue_date = fields.Date(
        string="Issue Date",
        default=fields.Date.context_today,
        tracking=True,
    )

    onboard_date = fields.Date(
        string="On Board Date",
        tracking=True,
        help="Sea: shipped-on-board endorsement date. Air: cargo "
             "received date.",
    )

    # ----- Parties -----

    shipper_id = fields.Many2one("res.partner", string="Shipper", index=True, tracking=True)
    consignee_id = fields.Many2one("res.partner", string="Consignee", index=True, tracking=True)
    notify_party_id = fields.Many2one("res.partner", string="Notify Party", tracking=True)

    carrier_id = fields.Many2one(
        "res.partner",
        string="Carrier",
        index=True,
        tracking=True,
        help="Issuing carrier (shipping line for sea, airline for air).",
    )

    # ----- Mode-specific (sea) -----

    vessel_name = fields.Char(string="Vessel", help="Sea only.")
    voyage_number = fields.Char(string="Voyage", help="Sea only.")

    # ----- Mode-specific (air) -----

    flight_number = fields.Char(string="Flight", help="Air only.")

    # ----- Lane snapshot -----

    pol_name = fields.Char(string="Port or Airport of Loading")
    pod_name = fields.Char(string="Port or Airport of Discharge")
    place_of_receipt = fields.Char(string="Place of Receipt")
    place_of_delivery = fields.Char(string="Place of Delivery")

    # ----- Terms -----

    incoterm_id = fields.Many2one("account.incoterms", string="Incoterm")
    freight_payment_terms = fields.Selection(
        selection=[
            ("prepaid", "Prepaid"),
            ("collect", "Collect"),
        ],
        string="Freight Terms",
    )
    release_type = fields.Selection(
        selection=[
            ("original", "Original BL"),
            ("seaway", "Seaway"),
            ("telex", "Telex Release"),
            ("express", "Express Release"),
        ],
        string="Release Type",
    )

    # ----- Cargo summary -----

    cargo_description = fields.Text(string="Cargo Description")
    package_count = fields.Integer(string="Packages")
    gross_weight_kg = fields.Float(string="Gross Weight (kg)")
    volume_cbm = fields.Float(string="Volume (m3)")
    chargeable_weight_kg = fields.Float(string="Chargeable Weight (kg)", help="Air: max(actual, volumetric).")

    container_ids = fields.One2many(
        "eh.log.freight.container",
        "bl_id",
        string="Containers",
    )

    container_count = fields.Integer(
        string="Containers",
        compute="_compute_container_count",
    )

    # ----- Internal linkage -----

    parent_bl_id = fields.Many2one(
        "eh.log.freight.bl",
        string="Parent BL",
        help="For HBL or HAWB, points to the consolidating MBL or "
             "MAWB. Drives the consolidation report.",
        domain="[('bl_type', 'in', ('mbl', 'mawb'))]",
    )

    child_bl_ids = fields.One2many(
        "eh.log.freight.bl",
        "parent_bl_id",
        string="House BLs",
    )

    company_id = fields.Many2one(
        related="job_id.company_id",
        store=True,
        index=True,
    )

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_freight_bl_company_rel",
        "bl_id",
        "company_id",
        string="Companies",
        compute="_compute_company_ids",
        store=True,
        index=True,
    )

    # ----- SQL constraints -----

    _sql_constraints = [
        (
            'number_unique_per_company',
            'UNIQUE(company_id, bl_type, number)',
            'Bill of lading number must be unique per (company, type). If you are receiving a duplicate from a carrier, contact the carrier for clarification before recording it.',
        ),
    ]

    # ----- Computes -----

    @api.depends("company_id")
    def _compute_company_ids(self):
        for bl in self:
            bl.company_ids = bl.company_id

    @api.depends("container_ids")
    def _compute_container_count(self):
        for bl in self:
            bl.container_count = len(bl.container_ids)

    # ----- Lifecycle -----

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                seq_code = "eh.log.freight.bl"
                vals["name"] = self.env["ir.sequence"].next_by_code(seq_code) or _("New")
        return super().create(vals_list)

    @api.constrains("bl_type", "number", "state")
    def _check_number_required_at_issue(self):
        for bl in self:
            if bl.state in ("issued", "released", "closed") and not bl.number:
                raise UserError(_(
                    "[EHL-BL-001] %(name)s cannot be issued without a "
                    "BL number. Capture the carrier-issued number first."
                ) % {"name": bl.name})

    # ----- State transitions -----

    def _transition_state(self, target_state: str):
        for bl in self:
            current = bl.state
            allowed = ALLOWED_BL_TRANSITIONS.get(current, set())
            if target_state not in allowed:
                raise JobStateConflictError(
                    5,
                    _(
                        "Bill of lading %(name)s cannot move from "
                        "%(current)s to %(target)s. Allowed transitions "
                        "from %(current)s: %(allowed)s."
                    ) % {
                        "name": bl.name,
                        "current": current,
                        "target": target_state,
                        "allowed": ", ".join(sorted(allowed)) or _("(none)"),
                    },
                )
            bl.with_context(eh_log_freight_bl_internal_state_write=True).write({
                "state": target_state,
            })
            self.env["eh.log.event"].log(
                category="state_transition",
                summary=_("Bill of lading %(name)s moved to %(state)s.") % {
                    "name": bl.name, "state": target_state,
                },
                related_model="eh.log.freight.bl",
                related_record_id=bl.id,
                related_record_display=bl.name,
                context={
                    "from_state": current,
                    "to_state": target_state,
                    "bl_type": bl.bl_type,
                    "bl_number": bl.number,
                },
            )

    def write(self, vals):
        if "state" in vals and not self.env.context.get("eh_log_freight_bl_internal_state_write"):
            raise UserError(_(
                "[EHL-BL-002] State changes on a bill of lading must "
                "go through the action buttons. Direct writes are rejected."
            ))
        return super().write(vals)

    def action_issue(self):
        self._transition_state("issued")
        return True

    def action_release(self):
        self._transition_state("released")
        return True

    def action_close(self):
        self._transition_state("closed")
        return True

    def action_cancel(self):
        self._transition_state("cancelled")
        return True
