# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Milestone instance on a freight job.

One row per milestone-type instance per job. Carries planned and
actual datetime, source (manual, EDI, telematics, adapter, customer
portal), and computed variance.
"""
from odoo import _, api, fields, models


class EhLogFreightMilestone(models.Model):
    _name = "eh.log.freight.milestone"
    _description = "Freight Milestone"
    _order = "job_id, sequence, planned_at"
    _rec_name = "type_id"

    job_id = fields.Many2one(
        "eh.log.freight.job",
        string="Job",
        required=True,
        ondelete="cascade",
        index=True,
    )

    type_id = fields.Many2one(
        "eh.log.freight.milestone.type",
        string="Milestone",
        required=True,
        ondelete="restrict",
        index=True,
    )

    sequence = fields.Integer(
        related="type_id.sequence",
        store=True,
    )

    planned_at = fields.Datetime(
        string="Planned",
        index=True,
    )

    actual_at = fields.Datetime(
        string="Actual",
        index=True,
    )

    variance_hours = fields.Float(
        string="Variance (hours)",
        compute="_compute_variance",
        store=True,
        help="Actual minus planned in hours. Positive means late, "
             "negative means early. Empty when either side is missing.",
    )

    source = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("edi", "EDI"),
            ("adapter", "Adapter"),
            ("telematics", "Telematics"),
            ("portal", "Customer Portal"),
            ("api", "API"),
        ],
        string="Source",
        default="manual",
        required=True,
    )

    notes = fields.Char(string="Notes")

    company_id = fields.Many2one(
        related="job_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("planned_at", "actual_at")
    def _compute_variance(self):
        for milestone in self:
            if milestone.planned_at and milestone.actual_at:
                delta = milestone.actual_at - milestone.planned_at
                milestone.variance_hours = delta.total_seconds() / 3600.0
            else:
                milestone.variance_hours = 0.0

    _sql_constraints = [
        (
            'job_type_unique',
            'UNIQUE(job_id, type_id)',
            'Each milestone type may appear only once per job. Edit the existing row instead of creating a duplicate.',
        ),
    ]
