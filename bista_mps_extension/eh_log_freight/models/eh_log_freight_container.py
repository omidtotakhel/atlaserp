# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Container or ULD instance on a freight job.

One row per piece of equipment moving on the job. For sea FCL the
type is a container ISO type; for air the same model is reused with
an air ULD selected (ULD type catalogue lives separately and is
extended in a later module).

Container number validation is the ISO 6346 check digit algorithm,
applied at save time. A manual override flag exists for the
exceptional case of a known-typo number that needs to flow through
unchanged for traceability.
"""
import logging
import re
import string

from odoo import _, api, fields, models

from odoo.addons.eh_log_base.exceptions import EhLogValidationError

_logger = logging.getLogger(__name__)

CONTAINER_NUMBER_RE = re.compile(r"^[A-Z]{4}\d{7}$")
ISO_LETTER_VALUES = {
    letter: value for letter, value in zip(
        # Standard ISO 6346 letter-to-value mapping. Skip 11, 22, 33.
        string.ascii_uppercase,
        [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25,
         26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38],
    )
}


def _iso6346_check_digit(serial: str) -> int:
    """Compute the ISO 6346 check digit for an 11-character container number.

    Input must be the leading 10 characters (4 letters + 6 digits)
    plus the check digit position; only the leading 10 are used.
    Returns the expected check digit as an integer 0..9.
    """
    if len(serial) < 10:
        return -1
    total = 0
    for index, char in enumerate(serial[:10]):
        if char.isalpha():
            value = ISO_LETTER_VALUES.get(char)
            if value is None:
                return -1
        else:
            value = int(char)
        total += value * (2 ** index)
    return total % 11 % 10


class EhLogFreightContainer(models.Model):
    _name = "eh.log.freight.container"
    _description = "Freight Container or ULD"
    _order = "job_id, sequence, container_number"
    _rec_name = "container_number"

    job_id = fields.Many2one(
        "eh.log.freight.job",
        string="Job",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(default=10)

    iso_type_id = fields.Many2one(
        "eh.log.freight.container.iso.type",
        string="ISO Type",
        required=True,
        ondelete="restrict",
        index=True,
        help=(
            "ISO 6346 size/type code (e.g. 22G1 = 20ft general purpose, 42G1 = 40ft general, 45R1 = 40ft HC reefer). Drives capacity defaults and reefer / DG flags."
        )
    )

    container_number = fields.Char(
        string="Container No.",
        index=True,
        size=11,
        help="ISO 6346 container number: 4 letters (owner code + "
             "category) + 6 digits (serial) + 1 check digit. Validated "
             "on save unless 'Manual Override' is set.",
    )

    seal_number = fields.Char(string="Seal No.")

    bl_id = fields.Many2one(
        "eh.log.freight.bl",
        string="Bill of Lading",
        index=True,
        help="Optional link to the bill of lading carrying this "
             "container. Set automatically when a BL line references "
             "the container.",
    )

    gross_weight_kg = fields.Float(string="Gross Weight (kg)")

    volume_cbm = fields.Float(string="Volume (m3)")

    cargo_description = fields.Text(string="Cargo Description")

    package_count = fields.Integer(string="Packages")

    pickup_at = fields.Datetime(string="Picked Up")
    gate_in_at = fields.Datetime(string="Gate-In")
    loaded_at = fields.Datetime(string="Loaded On Board")
    discharged_at = fields.Datetime(string="Discharged")
    gate_out_at = fields.Datetime(string="Gate-Out")
    returned_at = fields.Datetime(string="Returned to Depot")

    state = fields.Selection(
        selection=[
            ("planned", "Planned"),
            ("picked_up", "Picked Up"),
            ("at_terminal", "At Terminal"),
            ("on_board", "On Board"),
            ("at_destination", "At Destination"),
            ("delivered", "Delivered"),
            ("returned", "Returned"),
        ],
        string="State",
        compute="_compute_state",
        store=True,
        index=True,
    )

    manual_number_override = fields.Boolean(
        string="Manual Number Override",
        help="Skip ISO 6346 check digit validation. Use only for "
             "known-bad numbers from upstream documents that must "
             "flow through unchanged for traceability.",
    )

    company_id = fields.Many2one(
        related="job_id.company_id",
        store=True,
        index=True,
    )

    @api.depends(
        "pickup_at", "gate_in_at", "loaded_at",
        "discharged_at", "gate_out_at", "returned_at",
    )
    def _compute_state(self):
        for container in self:
            if container.returned_at:
                container.state = "returned"
            elif container.gate_out_at:
                container.state = "delivered"
            elif container.discharged_at:
                container.state = "at_destination"
            elif container.loaded_at:
                container.state = "on_board"
            elif container.gate_in_at:
                container.state = "at_terminal"
            elif container.pickup_at:
                container.state = "picked_up"
            else:
                container.state = "planned"

    @api.constrains("container_number", "manual_number_override")
    def _check_container_number(self):
        for container in self:
            if not container.container_number:
                continue
            if container.manual_number_override:
                continue
            number = container.container_number.strip().upper()
            if not CONTAINER_NUMBER_RE.match(number):
                raise EhLogValidationError(
                    3,
                    _(
                        "Container number %(num)s does not match the "
                        "ISO 6346 format (4 letters + 7 digits, e.g. "
                        "MSCU1234567). Either fix the number, set "
                        "Manual Number Override, or untick the check."
                    ) % {"num": container.container_number},
                )
            expected = _iso6346_check_digit(number)
            actual = int(number[-1])
            if expected != actual:
                raise EhLogValidationError(
                    4,
                    _(
                        "Container number %(num)s fails the ISO 6346 "
                        "check digit. Expected check digit %(expected)d, "
                        "got %(actual)d. Either correct the number or "
                        "set Manual Number Override if you have verified "
                        "the discrepancy is intentional."
                    ) % {
                        "num": number,
                        "expected": expected,
                        "actual": actual,
                    },
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("container_number"):
                vals["container_number"] = vals["container_number"].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if "container_number" in vals and vals["container_number"]:
            vals["container_number"] = vals["container_number"].strip().upper()
        return super().write(vals)
