# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Standardised charge codes for logistics quotations and invoices.

Why this is master data, not a tag list on sale.order.line: rate
sheets, surcharges, and accounting analytics all key on the same set
of charge codes. Centralising lets the rate engine, the invoicing
flow, and the gross-margin computation share one vocabulary.

A small starter set ships in data/eh_log_charge_code_data.xml so a
fresh install has the universally recognised codes (Origin THC,
Destination THC, Ocean Freight, BAF, ISPS, ENS, AMS, etc.). Country
localisation modules add country-specific codes (e.g. Mirsal stamp
duty for UAE customs).
"""
from odoo import _, api, fields, models


class EhLogChargeCode(models.Model):
    _name = "eh.log.charge.code"
    _description = "Logistics Charge Code"
    _order = "category, code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Stable identifier referenced from rate sheets and invoice "
             "lines. Convention: short uppercase alphanumeric, e.g. "
             "OFR for Ocean Freight, OTHC for Origin Terminal Handling.",
    )

    name = fields.Char(
        string="Description",
        required=True,
        translate=True,
    )

    category = fields.Selection(
        selection=[
            ("freight", "Freight"),
            ("origin", "Origin Charges"),
            ("destination", "Destination Charges"),
            ("surcharge", "Surcharge"),
            ("customs", "Customs and Duties"),
            ("documentation", "Documentation"),
            ("inland", "Inland Transport"),
            ("warehousing", "Warehousing and Handling"),
            ("insurance", "Insurance"),
            ("ancillary", "Ancillary"),
        ],
        string="Category",
        required=True,
        index=True,
    )

    direction = fields.Selection(
        selection=[
            ("import", "Import"),
            ("export", "Export"),
            ("both", "Both"),
        ],
        string="Direction",
        default="both",
        required=True,
    )

    mode = fields.Selection(
        selection=[
            ("any", "Any Mode"),
            ("sea", "Sea"),
            ("air", "Air"),
            ("road", "Road"),
            ("rail", "Rail"),
            ("multimodal", "Multimodal"),
            ("courier", "Courier or Express"),
        ],
        string="Mode",
        default="any",
        required=True,
        help="Filters rate-sheet selection so an air-only charge does "
             "not surface on a sea-freight quotation.",
    )

    default_currency_id = fields.Many2one(
        "res.currency",
        string="Default Currency",
        help="Optional default for rate sheets. Quotation currency wins "
             "when the two differ; this is a hint for the rate-sheet "
             "editor only.",
    )

    default_revenue_account_id = fields.Many2one(
        "account.account",
        string="Default Revenue Account",
        domain="[('account_type', '=', 'income')]",
        company_dependent=True,
        help="Posted on customer invoice lines billed against this "
             "charge code. Per-company because account hierarchies vary.",
    )

    default_expense_account_id = fields.Many2one(
        "account.account",
        string="Default Expense Account",
        domain="[('account_type', '=', 'expense')]",
        company_dependent=True,
        help="Posted on vendor bill lines costed against this charge "
             "code. Per-company because account hierarchies vary.",
    )

    is_disbursement = fields.Boolean(
        string="Disbursement",
        default=False,
        help="Disbursement charges are passed through at cost; the "
             "margin guard ignores them when checking gross margin.",
    )

    is_taxable_at_destination = fields.Boolean(
        string="Taxable at Destination",
        default=True,
        help="Hint for the tax engine in the customs broker module. "
             "When False, the charge is exempt at destination clearance.",
    )

    description = fields.Text(
        string="Detail",
        translate=True,
        help="Free-form notes for the operator. Surfaced on the rate "
             "sheet editor and on charge-line tooltips in quotations.",
    )

    active = fields.Boolean(default=True)

    product_id = fields.Many2one(
        "product.product",
        string="Service Product",
        domain="[('type', '=', 'service')]",
        ondelete="set null",
        help="Service product carried by quotation and invoice lines "
             "billed against this charge code. Odoo requires every "
             "billable order line to reference a product before the "
             "order can be confirmed or invoiced; logistics charge "
             "lines reuse this one. Left empty, it is auto-provisioned "
             "the first time the code is sold so operators never have to "
             "maintain a parallel product catalogue.",
    )

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_charge_code_company_rel",
        "charge_code_id",
        "company_id",
        string="Companies",
        help="Leave empty to make this code available across all "
             "companies. Use to scope a code to specific companies.",
    )

    _sql_constraints = [
        (
            'code_unique',
            'UNIQUE(code)',
            'Charge code must be unique. Pick a different code or edit the existing one instead of duplicating.',
        ),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"[{record.code}] {record.name}" if record.code else record.name
            )

    def _eh_log_get_product(self):
        """Return the service product for this charge code, provisioning
        one on first use.

        Logistics quotations bill standardised charges (Ocean Freight,
        THC, customs clearance, etc.) rather than catalogue products, so
        operators do not maintain a product per charge by hand. Odoo
        nonetheless requires a product on every confirmable, invoiceable
        line. We bridge the two by lazily creating a single service
        product the first time a code is actually sold and caching it on
        the code. The product is a company-shared service so the same
        code behaves identically across companies.
        """
        self.ensure_one()
        if self.product_id:
            return self.product_id
        product = self.env["product.product"].sudo().create({
            "name": self.name or self.code,
            "default_code": self.code,
            "type": "service",
            "sale_ok": True,
            "purchase_ok": True,
            "invoice_policy": "order",
            "list_price": 0.0,
            "taxes_id": [(5, 0, 0)],
        })
        self.sudo().product_id = product
        return product
