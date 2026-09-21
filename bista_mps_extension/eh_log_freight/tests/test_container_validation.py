# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Container ISO 6346 validation, state computation, manual override."""
from odoo.addons.eh_log_base.exceptions import EhLogValidationError
from odoo.addons.eh_log_freight.models.eh_log_freight_container import (
    _iso6346_check_digit,
)

from .common import EhLogFreightTestCase


class TestContainerValidation(EhLogFreightTestCase):

    def setUp(self):
        super().setUp()
        order = self._build_logistics_sale_order()
        self.job = self._confirm_and_get_job(order)
        self.iso_40hc = self.env.ref("eh_log_freight.iso_45g1")

    def test_iso6346_check_digit_known_values(self):
        # Owner+serial MSCU123456 has ISO 6346 check digit 6, so the
        # valid number is MSCU1234566. CSQU3054383 is the canonical
        # textbook example (check digit 3).
        self.assertEqual(_iso6346_check_digit("MSCU1234566"), 6)
        self.assertEqual(_iso6346_check_digit("CSQU3054383"), 3)

    def test_valid_container_number_accepted(self):
        # MSCU1234566 has check digit 6.
        container = self.env["eh.log.freight.container"].create({
            "job_id": self.job.id,
            "iso_type_id": self.iso_40hc.id,
            "container_number": "MSCU1234566",
        })
        self.assertTrue(container.id)

    def test_invalid_format_rejected(self):
        with self.assertRaises(EhLogValidationError) as ctx:
            self.env["eh.log.freight.container"].create({
                "job_id": self.job.id,
                "iso_type_id": self.iso_40hc.id,
                "container_number": "INVALID",
            })
        self.assertIn("[EHL-BASE-003]", str(ctx.exception))

    def test_wrong_check_digit_rejected(self):
        # Correct check digit for MSCU123456 is 6; 0 is therefore wrong.
        with self.assertRaises(EhLogValidationError) as ctx:
            self.env["eh.log.freight.container"].create({
                "job_id": self.job.id,
                "iso_type_id": self.iso_40hc.id,
                "container_number": "MSCU1234560",
            })
        self.assertIn("[EHL-BASE-004]", str(ctx.exception))

    def test_manual_override_skips_validation(self):
        container = self.env["eh.log.freight.container"].create({
            "job_id": self.job.id,
            "iso_type_id": self.iso_40hc.id,
            "container_number": "MSCU0000000",
            "manual_number_override": True,
        })
        self.assertTrue(container.id)

    def test_state_computed_from_timeline(self):
        from datetime import datetime
        container = self.env["eh.log.freight.container"].create({
            "job_id": self.job.id,
            "iso_type_id": self.iso_40hc.id,
            "container_number": "MSCU1234566",
        })
        self.assertEqual(container.state, "planned")
        container.pickup_at = datetime(2026, 6, 1, 8, 0)
        container.invalidate_recordset()
        self.assertEqual(container.state, "picked_up")
        container.gate_in_at = datetime(2026, 6, 1, 12, 0)
        container.invalidate_recordset()
        self.assertEqual(container.state, "at_terminal")
        container.loaded_at = datetime(2026, 6, 2, 6, 0)
        container.invalidate_recordset()
        self.assertEqual(container.state, "on_board")
        container.gate_out_at = datetime(2026, 6, 20, 14, 0)
        container.invalidate_recordset()
        self.assertEqual(container.state, "delivered")
        container.returned_at = datetime(2026, 6, 22, 8, 0)
        container.invalidate_recordset()
        self.assertEqual(container.state, "returned")

    def test_number_normalised_uppercase(self):
        container = self.env["eh.log.freight.container"].create({
            "job_id": self.job.id,
            "iso_type_id": self.iso_40hc.id,
            "container_number": " mscu1234566 ",
        })
        self.assertEqual(container.container_number, "MSCU1234566")
