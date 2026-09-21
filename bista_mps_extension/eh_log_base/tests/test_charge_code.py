# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Charge code constraints and seed integrity."""
from psycopg2 import IntegrityError
from odoo.tools.misc import mute_logger

from .common import EhLogIntegrationTestCase


SEED_CODES_REQUIRED = [
    "OFR", "AFR", "RFR", "OTHC", "DTHC",
    "BAF", "FSC", "ISPS", "CLRNC", "DUTY",
    "VAT-IMP", "BL-FEE", "AWB-FEE", "INS",
]


class TestChargeCodeConstraints(EhLogIntegrationTestCase):

    def test_code_unique(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["eh.log.charge.code"].create({
                    "code": "OFR",
                    "name": "Duplicate Ocean Freight",
                    "category": "freight",
                    "mode": "sea",
                })

    def test_seed_codes_present(self):
        ChargeCode = self.env["eh.log.charge.code"]
        for code in SEED_CODES_REQUIRED:
            record = ChargeCode.search([("code", "=", code)])
            self.assertEqual(
                len(record), 1,
                f"Seed charge code {code} missing or duplicated.",
            )

    def test_disbursement_flag_on_duty(self):
        duty = self.env.ref("eh_log_base.charge_code_duty")
        self.assertTrue(
            duty.is_disbursement,
            "DUTY charge code must be flagged as disbursement so the "
            "margin guard does not include it in margin computation.",
        )

    def test_display_name_format(self):
        ofr = self.env.ref("eh_log_base.charge_code_ofr")
        self.assertIn("OFR", ofr.display_name)
        self.assertIn("Ocean Freight", ofr.display_name)
