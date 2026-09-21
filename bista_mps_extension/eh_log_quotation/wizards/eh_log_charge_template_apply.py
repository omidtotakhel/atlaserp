# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Apply a charge template to a sale order.

Each template line becomes a sale order line carrying the charge code
and leg classification. The wizard preserves existing lines by default
(append mode); operators can flip ``replace_existing`` to delete the
existing logistics charge lines first (non-logistics lines, which are
identified by an empty charge code, are always preserved).
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EhLogChargeTemplateApply(models.TransientModel):
    _name = "eh.log.charge.template.apply"
    _description = "Apply Charge Template Wizard"

    order_id = fields.Many2one(
        "sale.order",
        string="Quotation",
        required=True,
        ondelete="cascade",
    )

    template_id = fields.Many2one(
        "eh.log.charge.template",
        string="Template",
        required=True,
        domain="['|', ('company_ids', '=', False), ('company_ids', 'in', allowed_company_id and [allowed_company_id] or [])]",
        help="Pick the template to apply. Templates that scope to "
             "specific companies are filtered to the current company.",
    )

    replace_existing = fields.Boolean(
        string="Replace Existing Charge Lines",
        default=False,
        help="When checked, existing logistics charge lines (lines "
             "carrying a charge code) are removed before the template "
             "lines are appended. Non-logistics product lines are "
             "always preserved.",
    )

    line_count = fields.Integer(
        string="Lines in Template",
        related="template_id.line_count",
        readonly=True,
    )

    allowed_company_id = fields.Many2one(
        "res.company",
        related="order_id.company_id",
        readonly=True,
    )

    def action_apply(self):
        self.ensure_one()
        if not self.template_id.line_ids:
            raise UserError(_(
                "[EHL-TEMPLATE-001] Template %(name)s has no lines. "
                "Add lines to the template first."
            ) % {"name": self.template_id.display_name})
        order = self.order_id
        if self.replace_existing:
            existing = order.order_line.filtered(
                lambda l: l.eh_log_charge_code_id
            )
            existing.unlink()
        # Build the new line vals.
        SaleOrderLine = self.env["sale.order.line"]
        for template_line in self.template_id.line_ids:
            description = (
                template_line.description
                or template_line.charge_code_id.name
                or template_line.charge_code_id.code
            )
            SaleOrderLine.create({
                "order_id": order.id,
                "name": description,
                "product_uom_qty": template_line.default_quantity,
                "price_unit": template_line.default_unit_price,
                "eh_log_charge_code_id": template_line.charge_code_id.id,
                "eh_log_leg": template_line.leg,
                "purchase_price": template_line.default_planned_cost,
            })
        order.write({
            "eh_log_charge_template_id": self.template_id.id,
            "eh_log_is_logistics": True,
        })
        # Onchange-like sync: pull mode and direction from the template
        # if the order has nothing set yet.
        if not order.eh_log_mode and self.template_id.mode != "any":
            order.eh_log_mode = self.template_id.mode
        if not order.eh_log_direction and self.template_id.direction != "any":
            order.eh_log_direction = self.template_id.direction
        if not order.eh_log_origin_country_id and self.template_id.origin_country_id:
            order.eh_log_origin_country_id = self.template_id.origin_country_id
        if not order.eh_log_destination_country_id and self.template_id.destination_country_id:
            order.eh_log_destination_country_id = self.template_id.destination_country_id
        order.message_post(body=Markup(
            _("Charge template <strong>%(name)s</strong> applied: "
              "%(count)s line(s) added.")
        ) % {
            "name": self.template_id.display_name,
            "count": len(self.template_id.line_ids),
        })
        return {
            "type": "ir.actions.act_window",
            "name": order.name,
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }
