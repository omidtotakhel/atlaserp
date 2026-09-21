# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Milestone types: the catalogue of named milestones a job can carry.

Centralised so the job's milestone timeline keys against a stable
master list. New verticals (rail, intercountry, project cargo) add
their own milestone types via data records; the engine never
hardcodes a milestone code.
"""
from odoo import _, api, fields, models


class EhLogFreightMilestoneType(models.Model):
    _name = "eh.log.freight.milestone.type"
    _description = "Freight Milestone Type"
    _order = "mode, sequence, code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Stable identifier (BOOKED, GATE_IN, VESSEL_SAILED, "
             "VESSEL_ARRIVED, GATE_OUT, DELIVERED, CUSTOMS_CLEARED, "
             "POD_RECEIVED, ...).",
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

    sequence = fields.Integer(default=10)

    is_terminal = fields.Boolean(
        string="Closes the Job",
        help="When checked, recording an actual datetime for this "
             "milestone advances the job into its terminal closed state.",
    )

    is_required = fields.Boolean(
        string="Required",
        default=False,
        help="When checked, the milestone is auto-added to every "
             "job timeline matching the mode.",
    )

    description = fields.Text(translate=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'code_unique',
            'UNIQUE(code)',
            'Milestone type code must be unique.',
        ),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"[{record.code}] {record.name}" if record.code else record.name
            )
