# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Sale order extension for freight job spawning.

When a logistics sale order is confirmed, this hook spawns one
forwarding job per (mode + direction) tuple represented on the order.
Cancelling the order cancels any non-cancelled freight job spawned
from it; re-confirming reuses an existing draft job instead of
spawning a duplicate.
"""
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    eh_log_freight_job_ids = fields.One2many(
        "eh.log.freight.job",
        "sale_order_id",
        string="Freight Jobs",
        copy=False,
        readonly=True,
    )

    eh_log_freight_job_count = fields.Integer(
        string="Freight Jobs",
        compute="_compute_eh_log_freight_job_count",
        store=True,
        compute_sudo=True,
    )

    eh_log_attach_freight_job_id = fields.Many2one(
        "eh.log.freight.job",
        string="Attach to existing job",
        copy=False,
        domain="[('customer_id', '=', partner_id), ('state', 'not in', ('closed', 'cancelled'))]",
        help="Optional. When set, confirming this quotation does NOT "
             "spawn a new freight job; the lines on this order are "
             "treated as additional revenue / cost lines for the "
             "selected existing job. Use this when you raise an "
             "extra charge (additional THC, demurrage, customs query "
             "fee, etc.) against a freight job that's already in flight.",
    )

    @api.depends("eh_log_freight_job_ids", "eh_log_freight_job_ids.state")
    def _compute_eh_log_freight_job_count(self):
        for order in self:
            order.eh_log_freight_job_count = len(
                order.eh_log_freight_job_ids.filtered(
                    lambda j: j.state != "cancelled"
                )
            )

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            if not order.eh_log_is_logistics:
                continue

            # Branch 1: this order is attached to an existing freight job
            # (an additional-charge or variation order). Do not spawn;
            # link the order to the existing job and post a note.
            if order.eh_log_attach_freight_job_id:
                target = order.eh_log_attach_freight_job_id.sudo()
                if target.state in ("closed", "cancelled"):
                    raise UserError(_(
                        "Cannot attach to freight job %(name)s because it "
                        "is %(state)s. Only open jobs accept new attached "
                        "orders; for closed jobs raise a Variation."
                    ) % {"name": target.name, "state": target.state})
                order.message_post(body=Markup(
                    _("This order's lines are attached to existing freight "
                      "job <strong>%(name)s</strong>. No new job spawned.")
                ) % {"name": target.name})
                target.message_post(body=Markup(
                    _("Sale order <strong>%(so)s</strong> attached as an "
                      "additional charge / variation source.")
                ) % {"so": order.name})
                continue

            # Branch 2: standard logistics quote - spawn a freight job
            # if mode + direction are present.
            if not (order.eh_log_mode and order.eh_log_direction):
                continue
            existing = self.env["eh.log.freight.job"].sudo().search([
                ("sale_order_id", "=", order.id),
                ("state", "!=", "cancelled"),
            ], limit=1)
            if existing:
                order.message_post(body=Markup(
                    _("Freight job <strong>%(name)s</strong> already exists for "
                      "this order; skipping duplicate spawn.")
                ) % {"name": existing.name})
                continue

            # The order may have been confirmed, cancelled (which cancels
            # its job), drafted, and confirmed again. Rather than leave an
            # orphan cancelled job and spawn a fresh one, revive the most
            # recent cancelled job so the order keeps a single job across
            # cancel/re-confirm cycles.
            revived = self.env["eh.log.freight.job"].sudo().search([
                ("sale_order_id", "=", order.id),
                ("state", "=", "cancelled"),
            ], order="id desc", limit=1)
            if revived:
                revived.with_context(
                    eh_log_freight_internal_state_write=True
                ).write({"state": "draft"})
                order.message_post(body=Markup(
                    _("Freight job <strong>%(name)s</strong> reactivated on "
                      "re-confirmation.")
                ) % {"name": revived.name})
                continue
            order._eh_log_spawn_freight_job()
        return result

    def _action_cancel(self):
        """Cancel any spawned freight jobs when the sale order is cancelled.

        Uses sudo() because operators cancelling a sale order may not have
        write access on freight jobs. Only cancels non-terminal jobs;
        already-closed jobs remain (post-close changes flow through a
        variation, not a cancel).
        """
        result = super()._action_cancel()
        for order in self:
            jobs = self.env["eh.log.freight.job"].sudo().search([
                ("sale_order_id", "=", order.id),
                ("state", "not in", ("cancelled", "closed")),
            ])
            for job in jobs:
                try:
                    job.action_cancel()
                except Exception as exc:
                    _logger.warning(
                        "Could not auto-cancel freight job %s on SO cancel: %s",
                        job.name, exc,
                    )
                    continue
            if jobs:
                order.message_post(body=Markup(
                    _("Cancelled freight job(s): <strong>%(names)s</strong>.")
                ) % {"names": ", ".join(jobs.mapped("name"))})
        return result

    def _eh_log_spawn_freight_job(self):
        """Create the forwarding job from this confirmed order."""
        self.ensure_one()
        Job = self.env["eh.log.freight.job"].sudo()
        job = Job.create({
            "sale_order_id": self.id,
            "company_id": self.company_id.id,
            "mode": self.eh_log_mode,
            "direction": self.eh_log_direction,
            "origin_country_id": self.eh_log_origin_country_id.id,
            "destination_country_id": self.eh_log_destination_country_id.id,
            "origin_location": self.eh_log_origin_location,
            "destination_location": self.eh_log_destination_location,
            "incoterm_id": (
                self.incoterm.id
                if "incoterm" in self._fields and self.incoterm
                else False
            ),
            "customer_id": self.partner_id.id,
            "shipper_id": self.partner_shipping_id.id if self.partner_shipping_id else self.partner_id.id,
            "consignee_id": self.partner_invoice_id.id if self.partner_invoice_id else self.partner_id.id,
        })
        self.message_post(body=Markup(
            _("Freight job <strong>%(name)s</strong> spawned from this "
              "confirmation.")
        ) % {"name": job.name})
        return job

    def action_view_eh_log_freight_jobs(self):
        """Open the spawned freight job(s) for this sale order.

        Uses search() (not the One2many cache) so cancel/reconfirm
        cycles never leave the user staring at an empty list.
        Includes cancelled jobs in the list so the audit trail is
        visible.
        """
        self.ensure_one()
        Job = self.env["eh.log.freight.job"].sudo()
        jobs = Job.search([("sale_order_id", "=", self.id)])
        active_jobs = jobs.filtered(lambda j: j.state != "cancelled")
        if len(active_jobs) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Freight Job %s") % active_jobs.name,
                "res_model": "eh.log.freight.job",
                "view_mode": "form",
                "res_id": active_jobs.id,
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Freight Jobs from %s") % self.name,
            "res_model": "eh.log.freight.job",
            "view_mode": "list,kanban,form",
            "domain": [("sale_order_id", "=", self.id)],
            "context": {
                "default_sale_order_id": self.id,
                "search_default_filter_open": 0,
            },
            "target": "current",
        }
