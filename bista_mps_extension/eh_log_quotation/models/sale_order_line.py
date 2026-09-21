# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Sale order line extension for logistics."""
from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    eh_log_charge_code_id = fields.Many2one(
        "eh.log.charge.code",
        string="Charge Code",
        index=True,
        help="Standardised charge code for this line. Drives the "
             "leg classification, the tax tag default, and whether "
             "the line is included in the margin computation.",
    )

    eh_log_leg = fields.Selection(
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
        index=True,
    )

    eh_log_is_disbursement = fields.Boolean(
        string="Disbursement",
        compute="_compute_eh_log_is_disbursement",
        store=True,
        help="When True, the line is treated as pass-through and "
             "excluded from gross margin computation.",
    )

    @api.depends("eh_log_charge_code_id", "eh_log_charge_code_id.is_disbursement")
    def _compute_eh_log_is_disbursement(self):
        for line in self:
            line.eh_log_is_disbursement = bool(
                line.eh_log_charge_code_id
                and line.eh_log_charge_code_id.is_disbursement
            )

    # ------------------------------------------------------------------
    # Charge code -> service product bridge
    # ------------------------------------------------------------------
    # Odoo 19 refuses to confirm or invoice an order while any billable
    # line is missing a product (sale.order._confirmation_error_message
    # plus a database CHECK on sale.order.line). Logistics lines are
    # keyed by charge code, not catalogue product, so we transparently
    # attach the charge code's service product whenever a line carries a
    # charge code but no product. Provided name/price_unit are kept
    # because both are editable computed fields, so a value supplied at
    # create time wins over the product defaults.
    @api.model
    def _eh_log_generic_charge_product(self):
        """Shared service product used for logistics lines that carry no
        charge code (e.g. a free-text freight line). Provisioned once and
        located by its stable internal reference so a fresh install and a
        long-running database resolve the same product."""
        Product = self.env["product.product"]
        product = Product.sudo().search(
            [("default_code", "=", "EHLOG-CHARGE")], limit=1)
        if not product:
            product = Product.sudo().create({
                "name": "Logistics Charge",
                "default_code": "EHLOG-CHARGE",
                "type": "service",
                "sale_ok": True,
                "purchase_ok": True,
                "invoice_policy": "order",
                "list_price": 0.0,
                "taxes_id": [(5, 0, 0)],
            })
        return product

    @api.model
    def _eh_log_fill_product_in_vals(self, vals):
        if vals.get("product_id") or vals.get("display_type"):
            return vals
        product = None
        code_id = vals.get("eh_log_charge_code_id")
        if code_id:
            code = self.env["eh.log.charge.code"].browse(code_id)
            if code.exists():
                product = code._eh_log_get_product()
        if product is None:
            # No charge code: only logistics orders get a product injected
            # so plain product-less sales lines on ordinary quotations are
            # left untouched. A billable logistics line must carry a product
            # before the order can confirm or invoice.
            order_id = vals.get("order_id")
            if order_id:
                order = self.env["sale.order"].browse(order_id)
                if order.exists() and order.eh_log_is_logistics:
                    product = self._eh_log_generic_charge_product()
        if product is None and self.env.context.get("eh_log_force_charge_product"):
            # Programmatic charge sources (variations, disbursements,
            # storage billing) post billable lines onto an ordinary order;
            # the flag opts them into the same generic service product.
            product = self._eh_log_generic_charge_product()
        if product is None:
            return vals
        vals["product_id"] = product.id
        # The sale.order.line database CHECK requires the unit of measure
        # alongside the product. Its field name differs across versions
        # (product_uom on 16-18, product_uom_id on 19).
        uom_field = ("product_uom_id" if "product_uom_id" in self._fields
                     else "product_uom")
        if not vals.get(uom_field):
            vals[uom_field] = product.uom_id.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._eh_log_fill_product_in_vals(vals)
        lines = super().create(vals_list)
        lines._eh_log_flag_logistics_orders()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if vals.get("eh_log_charge_code_id") and not vals.get("product_id"):
            for line in self:
                if (
                    line.eh_log_charge_code_id
                    and not line.product_id
                    and not line.display_type
                ):
                    line.product_id = line.eh_log_charge_code_id._eh_log_get_product()
        if vals.get("eh_log_charge_code_id"):
            self._eh_log_flag_logistics_orders()
        return res

    def _eh_log_flag_logistics_orders(self):
        """Auto-flag the parent order as a logistics quotation as soon as
        any of its lines carries a charge code.

        The flag is only ever set, never cleared, so an operator who
        unticks it keeps control; the source of truth stays the
        eh_log_is_logistics field on the order. Auto-setting it means a
        quote built by adding charge-code lines does not silently miss
        the logistics workflow because someone forgot the checkbox.
        """
        orders = self.order_id.filtered(
            lambda o: not o.eh_log_is_logistics
            and any(line.eh_log_charge_code_id for line in o.order_line)
        )
        if orders:
            orders.eh_log_is_logistics = True

    @api.onchange("eh_log_charge_code_id")
    def _onchange_eh_log_charge_code_id(self):
        # Pre-fill the line description from the charge code name and
        # set sensible accounting defaults if a per-company default is
        # configured on the charge code.
        if self.eh_log_charge_code_id:
            if not self.name or self.name == "/":
                self.name = self.eh_log_charge_code_id.name
            company_currency = self.env.company.currency_id
            default_currency = (
                self.eh_log_charge_code_id.default_currency_id
                or company_currency
            )
            if not self.currency_id:
                self.currency_id = default_currency

    # Operators flip the Logistics checkbox explicitly. Auto-detection
    # by charge-code presence used to live here; it caused
    # non-logistics quotes to get logistics fields whenever a single
    # line happened to carry a charge code (which the apply-template
    # wizard does even on mixed orders). Removed - the source of truth
    # is the eh_log_is_logistics field on sale.order.
