# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Cargo and trade document types.

Centralised so the document checklist on jobs, the KYC workflow, the
customs declaration form, and the sale-order pre-flight all reference
the same vocabulary. A starter seed in data/eh_log_document_type_data.xml
covers the universally recognised documents (HBL, HAWB, MBL, MAWB,
Commercial Invoice, Packing List, Certificate of Origin, etc.).
Country and vertical modules append country-specific or mode-specific
documents.
"""
from odoo import _, api, fields, models


class EhLogDocumentType(models.Model):
    _name = "eh.log.document.type"
    _description = "Logistics Document Type"
    _order = "category, code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Stable short identifier (HBL, HAWB, MBL, MAWB, COI, COO, "
             "PL, COMINV, ...). Referenced from checklists.",
    )

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )

    category = fields.Selection(
        selection=[
            ("transport", "Transport Document"),
            ("commercial", "Commercial Document"),
            ("customs", "Customs Document"),
            ("regulatory", "Regulatory Certificate"),
            ("insurance", "Insurance"),
            ("identity", "Identity and KYC"),
            ("compliance", "Compliance and Sanctions"),
            ("financial", "Financial Document"),
            ("other", "Other"),
        ],
        string="Category",
        required=True,
        index=True,
    )

    is_required_default = fields.Boolean(
        string="Required by Default",
        default=False,
        help="When checked, the document is auto-added to the job "
             "checklist when applicable. Operators can still remove it "
             "for non-standard scenarios.",
    )

    expiry_aware = fields.Boolean(
        string="Tracks Expiry",
        default=False,
        help="When checked, the related upload captures an expiry date "
             "and the system raises a warning before expiry per the "
             "default warning days field.",
    )

    expiry_warning_days = fields.Integer(
        string="Default Expiry Warning (days)",
        default=30,
        help="How many days before expiry the system raises an activity "
             "to the document owner. 0 disables the warning.",
    )

    applies_to_modes = fields.Char(
        string="Applies To Modes",
        default="any",
        help="Comma-separated list of modes the document applies to "
             "(sea,air,road,rail,multimodal,courier) or 'any'. Used to "
             "filter the checklist when the job mode is set.",
    )

    description = fields.Text(translate=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'code_unique',
            'UNIQUE(code)',
            'Document type code must be unique.',
        ),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"[{record.code}] {record.name}" if record.code else record.name
            )
