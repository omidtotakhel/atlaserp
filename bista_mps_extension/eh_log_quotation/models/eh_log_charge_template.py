# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Charge template: a named bundle of charge codes per lane and mode.

A charge template is a re-usable rate snippet. A user composing a
quotation for a recurring lane (Jebel Ali to Dammam FCL 20', for
example) selects a template and the wizard appends its lines to the
sale order. Lines retain their charge code and leg classification so
the cost, revenue, and margin computations work the same as for hand-
entered lines.

Templates are not rate cards. The rate management module
(eh_log_rate_mgmt, future) is the place for time-bounded validity,
surcharge schedules, and contract negotiation. Templates are the
operator's quick-pick.
"""
from odoo import _, api, fields, models


class EhLogChargeTemplate(models.Model):
    _name = "eh.log.charge.template"
    _description = "Logistics Charge Template"
    _order = "mode, direction, name"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Stable short identifier (e.g. SEA-FCL-AE-SA-20). Used "
             "to recall the template by typed search rather than by "
             "scrolling the dropdown.",
    )

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
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
        index=True,
    )

    direction = fields.Selection(
        selection=[
            ("import", "Import"),
            ("export", "Export"),
            ("cross_trade", "Cross Trade"),
            ("any", "Any"),
        ],
        string="Direction",
        default="any",
        required=True,
    )

    origin_country_id = fields.Many2one(
        "res.country",
        string="Origin Country",
        help="Optional origin filter. When set, the template is only "
             "suggested for quotations whose origin country matches.",
    )

    destination_country_id = fields.Many2one(
        "res.country",
        string="Destination Country",
        help="Optional destination filter. When set, the template is "
             "only suggested for quotations whose destination country "
             "matches.",
    )

    default_currency_id = fields.Many2one(
        "res.currency",
        string="Default Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    line_ids = fields.One2many(
        "eh.log.charge.template.line",
        "template_id",
        string="Lines",
        copy=True,
    )

    description = fields.Text(translate=True)

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_charge_template_company_rel",
        "template_id",
        "company_id",
        string="Companies",
        help="Leave empty to share across all companies.",
    )

    active = fields.Boolean(default=True)

    line_count = fields.Integer(compute="_compute_line_count")

    _sql_constraints = [
        (
            'code_unique',
            'UNIQUE(code)',
            'Charge template code must be unique.',
        ),
    ]

    @api.depends("line_ids")
    def _compute_line_count(self):
        for template in self:
            template.line_count = len(template.line_ids)

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"[{record.code}] {record.name}" if record.code else record.name
            )
