# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Charge template line: one charge with default quantity and unit price."""
from odoo import _, api, fields, models


class EhLogChargeTemplateLine(models.Model):
    _name = "eh.log.charge.template.line"
    _description = "Logistics Charge Template Line"
    _order = "template_id, sequence, id"

    template_id = fields.Many2one(
        "eh.log.charge.template",
        string="Template",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(default=10)

    charge_code_id = fields.Many2one(
        "eh.log.charge.code",
        string="Charge Code",
        required=True,
        index=True,
        help="Standardised charge code from the ERP Heritage catalogue. "
             "The Apply Template wizard creates a sale order line "
             "carrying this code so reports and the margin guard work.",
    )

    leg = fields.Selection(
        selection=[
            ("origin", "Origin"),
            ("main", "Main Carriage"),
            ("destination", "Destination"),
            ("inland", "Inland"),
            ("customs", "Customs"),
            ("insurance", "Insurance"),
            ("other", "Other"),
        ],
        string="Leg",
        default="main",
        required=True,
    )

    default_quantity = fields.Float(
        string="Default Quantity",
        default=1.0,
        required=True,
    )

    default_unit_price = fields.Monetary(
        string="Default Unit Price",
        currency_field="currency_id",
        default=0.0,
    )

    default_planned_cost = fields.Monetary(
        string="Default Planned Cost",
        currency_field="currency_id",
        help="Per-unit planned procurement cost. Carried into the "
             "sale order line so the margin guard works the moment "
             "the template is applied. Operators refine when they "
             "have actual vendor quotes.",
    )

    currency_id = fields.Many2one(
        related="template_id.default_currency_id",
        store=True,
        readonly=True,
    )

    description = fields.Char(
        string="Description Override",
        translate=True,
        help="Optional override for the sale order line description. "
             "When empty, the charge code's name is used.",
    )

    @api.depends("charge_code_id", "default_quantity", "default_unit_price")
    def _compute_display_name(self):
        for line in self:
            label = line.charge_code_id.display_name or _("(no charge code)")
            line.display_name = f"{label} x {line.default_quantity}"
