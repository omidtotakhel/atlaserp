# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Mass-state wizard for freight jobs.

Operator picks N jobs in the list and advances them all in one
transaction. The state machine still validates each transition; jobs
that cannot move are quietly skipped and reported.
"""
from odoo import api, fields, models, _


TARGET_STATE_OPTIONS = [
    ("booked", "Booked"),
    ("in_transit", "In Transit"),
    ("at_destination", "At Destination"),
    ("delivered", "Delivered"),
    ("closed", "Closed"),
]

STATE_ACTION_MAP = {
    "booked": "action_book",
    "in_transit": "action_set_in_transit",
    "at_destination": "action_set_at_destination",
    "delivered": "action_set_delivered",
    "closed": "action_close",
}


class EhLogFreightMassAdvance(models.TransientModel):
    _name = "eh.log.freight.mass.advance"
    _description = "Mass-advance Freight Jobs"

    job_ids = fields.Many2many(
        "eh.log.freight.job",
        string="Freight Jobs",
        required=True,
    )
    target_state = fields.Selection(
        TARGET_STATE_OPTIONS,
        string="Target State",
        required=True,
        default="booked",
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            vals["job_ids"] = [(6, 0, active_ids)]
        return vals

    def action_apply(self):
        self.ensure_one()
        action_name = STATE_ACTION_MAP[self.target_state]
        moved = self.env["eh.log.freight.job"]
        skipped = self.env["eh.log.freight.job"]
        for job in self.job_ids:
            try:
                getattr(job, action_name)()
                moved |= job
            except Exception:
                skipped |= job
                continue
        title = _("Mass-advance complete")
        message = _(
            "Moved %(moved)d job(s) to %(state)s. Skipped %(skipped)d "
            "job(s) that were not in a compatible state."
        ) % {
            "moved": len(moved),
            "state": self.target_state,
            "skipped": len(skipped),
        }
        return self.env["eh.log.freight.job"]._notify_success(title, message)
