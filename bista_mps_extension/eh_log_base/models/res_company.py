# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Company-level logistics defaults.

A small set of fields the suite reads via env.company on hot paths
(margin guard threshold, default Incoterm, default mode, etc.). Most
configuration lives on res.config.settings; this model holds only what
is genuinely per-company and read frequently enough to justify its
own column rather than an ir.config_parameter lookup.
"""
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    eh_log_default_incoterm_id = fields.Many2one(
        "account.incoterms",
        string="Default Incoterm",
        help="Pre-fills new logistics quotations. Operators can change "
             "per quote.",
    )

    eh_log_default_mode = fields.Selection(
        selection=[
            ("sea", "Sea"),
            ("air", "Air"),
            ("road", "Road"),
            ("rail", "Rail"),
            ("multimodal", "Multimodal"),
            ("courier", "Courier or Express"),
        ],
        string="Default Logistics Mode",
        default="sea",
    )

    eh_log_margin_warning_threshold = fields.Float(
        string="Margin Warning Threshold (%)",
        default=15.0,
        help="Quotation margin below this percentage raises a warning "
             "in the form. Approval is still required only if the "
             "margin is below the company's hard floor.",
    )

    eh_log_margin_floor_threshold = fields.Float(
        string="Margin Approval Threshold (%)",
        default=8.0,
        help="Quotation margin below this percentage requires explicit "
             "manager approval before confirmation.",
    )

    eh_log_kyc_warning_days = fields.Integer(
        string="KYC Expiry Warning (days)",
        default=30,
        help="How many days before a KYC document expires the system "
             "creates an activity for the partner's account owner.",
    )

    eh_log_credit_warning_pct = fields.Float(
        string="Credit Exposure Warning (%)",
        default=80.0,
        help="When customer exposure crosses this percentage of the "
             "approved limit, new quotations raise a warning. The hard "
             "stop is always 100% of the limit.",
    )
