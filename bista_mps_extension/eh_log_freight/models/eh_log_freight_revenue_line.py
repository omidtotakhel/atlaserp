# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Job revenue ledger line.

Mirror of the cost ledger on the revenue side. Lines are entered
manually today, including adjustments and disbursement billing not
represented on the original quotation. The sale_order_line_id and
customer_invoice_line_id fields link a line to its billing source and
are provided for a future auto-population hook; nothing in this module
creates revenue lines automatically yet.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


REVENUE_STATE = [
    ("planned", "Planned"),
    ("invoiced", "Invoiced"),
    ("paid", "Paid"),
    ("cancelled", "Cancelled"),
]


class EhLogFreightRevenueLine(models.Model):
    _name = "eh.log.freight.revenue.line"
    _description = "Freight Job Revenue Line"
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
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        index=True,
    )

    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="SO Line",
        index=True,
        ondelete="set null",
    )

    customer_invoice_line_id = fields.Many2one(
        "account.move.line",
        string="Customer Invoice Line",
        index=True,
        ondelete="set null",
    )

    quantity = fields.Float(string="Quantity", default=1.0)

    unit_price = fields.Monetary(
        string="Unit Price",
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
        selection=REVENUE_STATE,
        string="State",
        default="planned",
        required=True,
        index=True,
    )

    invoice_date = fields.Date(string="Invoice Date", index=True)

    is_disbursement = fields.Boolean(
        string="Disbursement",
        compute="_compute_is_disbursement",
        store=True,
        help="Mirrors the charge code's disbursement flag. Disbursement "
             "lines are excluded from gross-margin computation.",
    )

    notes = fields.Text(string="Notes")

    company_id = fields.Many2one(
        related="job_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_price

    @api.depends("charge_code_id", "charge_code_id.is_disbursement")
    def _compute_is_disbursement(self):
        for line in self:
            line.is_disbursement = bool(
                line.charge_code_id
                and line.charge_code_id.is_disbursement
            )

    @api.depends("amount", "currency_id", "company_currency_id", "invoice_date")
    def _compute_amount_company_currency(self):
        for line in self:
            if not line.currency_id or line.currency_id == line.company_currency_id:
                line.amount_company_currency = line.amount
                continue
            line.amount_company_currency = line.currency_id._convert(
                line.amount,
                line.company_currency_id,
                line.company_id,
                line.invoice_date or fields.Date.context_today(line),
            )
