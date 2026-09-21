# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Document type constraints and seed integrity."""
from psycopg2 import IntegrityError
from odoo.tools.misc import mute_logger

from .common import EhLogIntegrationTestCase


REQUIRED_DOC_CODES = [
    "HBL", "MBL", "HAWB", "MAWB", "CMR",
    "COMINV", "PL", "DECL", "MFST", "DLVORD",
    "COO", "DGD", "ATA", "INSCERT",
    "TRDLIC", "VATREG", "PSPRT", "SCRN",
]


class TestDocumentType(EhLogIntegrationTestCase):

    def test_code_unique(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["eh.log.document.type"].create({
                    "code": "HBL",
                    "name": "Duplicate HBL",
                    "category": "transport",
                })

    def test_seed_documents_present(self):
        DocType = self.env["eh.log.document.type"]
        for code in REQUIRED_DOC_CODES:
            record = DocType.search([("code", "=", code)])
            self.assertEqual(
                len(record), 1,
                f"Seed document type {code} missing or duplicated.",
            )

    def test_expiry_aware_documents_have_warning_days(self):
        DocType = self.env["eh.log.document.type"]
        expiry_aware = DocType.search([("expiry_aware", "=", True)])
        self.assertTrue(expiry_aware, "Expected at least one expiry-aware doc type seeded.")
        for record in expiry_aware:
            self.assertGreater(
                record.expiry_warning_days, 0,
                f"{record.code} is expiry_aware but has expiry_warning_days "
                f"of {record.expiry_warning_days}; the warning will never fire.",
            )

    def test_display_name_format(self):
        hbl = self.env.ref("eh_log_base.doc_type_hbl")
        self.assertIn("HBL", hbl.display_name)
        self.assertIn("House Bill of Lading", hbl.display_name)
