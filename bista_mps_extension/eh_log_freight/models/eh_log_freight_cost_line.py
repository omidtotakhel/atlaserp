# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Job cost ledger line.

Each row represents one cost incurred against the freight job: a
purchase order line, a vendor bill line, or a manual accrual. The
state field tracks the line through planned -> committed -> accrued
-> invoiced as the procurement workflow progresses.

The ledger is the authoritative cost source for the job's actual
gross margin computation. Lines are entered manually today. The
purchase_order_line_id and vendor_bill_line_id fields link a line to
its procurement source and are provided for a future auto-population
hook; nothing in this module creates cost lines automatically yet.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


COST_STATE = [
    ("planned", "Planned"),
    ("committed", "Committed (PO)"),
    ("accrued", "Accrued"),
    ("invoiced", "Invoiced (Vendor Bill)"),
    ("cancelled", "Cancelled"),
]


class EhLogFreightCostLine(models.Model):
    _name = "eh.log.freight.cost.line"
    _description = "Freight Job Cost Line"
    _order = "job_id, sequence, id"
    _rec_name = "description"

    job_id = fields.Many2one(
        "eh.log.freight.job",
        string="Job",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(default=10)

    description = fields.Char(
        string="Description",
        required=True,
    )

    charge_code_id = fields.Many2one(
        "eh.log.charge.code",
        string="Charge Code",
        index=True,
        help="Standardised charge code so cost analytics group "
             "consistently with the corresponding revenue line.",
    )

    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        index=True,
    )

    purchase_order_line_id = fields.Many2one(
        "purchase.order.line",
        string="PO Line",
        index=True,
        ondelete="set null",
        help="Set when the cost was raised through procurement. "
             "Empty for manual accruals.",
    )

    vendor_bill_line_id = fields.Many2one(
        "account.move.line",
        string="Vendor Bill Line",
        index=True,
        ondelete="set null",
        help="Set when the cost has been billed by the vendor.",
    )

    quantity = fields.Float(string="Quantity", default=1.0)

    unit_cost = fields.Monetary(
        string="Unit Cost",
        currency_field="currency_id",
        required=True,
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    amount_company_currency = fields.Monetary(
        string="Amount (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_amount_company_currency",
        store=True,
    )

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        selection=COST_STATE,
        string="State",
        default="planned",
        required=True,
        index=True,
    )

    accrual_date = fields.Date(
        string="Accrual Date",
        default=fields.Date.context_today,
        index=True,
    )

    notes = fields.Text(string="Notes")

    company_id = fields.Many2one(
        related="job_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("quantity", "unit_cost")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_cost

    @api.depends("amount", "currency_id", "company_currency_id", "accrual_date")
    def _compute_amount_company_currency(self):
        for line in self:
            if not line.currency_id or line.currency_id == line.company_currency_id:
                line.amount_company_currency = line.amount
                continue
            line.amount_company_currency = line.currency_id._convert(
                line.amount,
                line.company_currency_id,
                line.company_id,
                line.accrual_date or fields.Date.context_today(line),
            )
