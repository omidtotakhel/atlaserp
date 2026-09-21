# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""ISO 6346 container type master.

Centralised so containers reference the same vocabulary across the
suite. Seeded with the universally-used container sizes; additional
specialised types (open-top, flat-rack, tank) are added via data
records by the project cargo and dangerous goods modules.
"""
from odoo import _, api, fields, models


class EhLogFreightContainerIsoType(models.Model):
    _name = "eh.log.freight.container.iso.type"
    _description = "Container ISO Type (ISO 6346)"
    _order = "code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        string="ISO Code",
        required=True,
        index=True,
        help="ISO 6346 size and type code (e.g. 22G1 for 20' Standard, "
             "42G1 for 40' Standard, 45G1 for 40' High Cube). The "
             "human-friendly short alias goes in alias_code.",
    )

    alias_code = fields.Char(
        string="Industry Alias",
        index=True,
        help="Common operator alias (20GP, 40GP, 40HC, 20RF, 40RF, "
             "20OT, 40FR, ...). Operators search by alias more than by "
             "the formal ISO code.",
    )

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )

    family = fields.Selection(
        selection=[
            ("dry", "Dry"),
            ("reefer", "Reefer"),
            ("open_top", "Open Top"),
            ("flat_rack", "Flat Rack"),
            ("tank", "Tank"),
            ("ventilated", "Ventilated"),
            ("bulk", "Bulk"),
            ("other", "Other"),
        ],
        string="Family",
        default="dry",
        required=True,
    )

    length_ft = fields.Integer(string="Length (ft)")

    height_high_cube = fields.Boolean(
        string="High Cube",
        help="True for 9'6\" containers; False for standard 8'6\".",
    )

    inner_volume_cbm = fields.Float(string="Inner Volume (m3)")

    max_payload_kg = fields.Float(string="Max Payload (kg)")

    max_gross_kg = fields.Float(string="Max Gross Weight (kg)")

    description = fields.Text(translate=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'code_unique',
            'UNIQUE(code)',
            'ISO container code must be unique.',
        ),
    ]

    @api.depends("code", "alias_code", "name")
    def _compute_display_name(self):
        for record in self:
            label = record.alias_code or record.code
            record.display_name = (
                f"[{label}] {record.name}" if label else record.name
            )
