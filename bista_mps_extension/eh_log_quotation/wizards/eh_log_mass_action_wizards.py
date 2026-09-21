# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Mass-action wizards for sale orders.

* Mass approval: manager picks N quotations from the list, approves
  them in one transaction, gets one toast.
* Mass send for review: bulk-tag the customer with a follow-up
  activity so the operator gets a single inbox of pending review
  conversations.
* Mass cancel: bulk-cancel a batch with one reason that records to
  every chatter.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EhLogQuotationMassApprove(models.TransientModel):
    _name = "eh.log.quotation.mass.approve"
    _description = "Mass-approve Logistics Quotations"

    order_ids = fields.Many2many(
        "sale.order",
        string="Quotations",
        required=True,
    )
    note = fields.Text(
        string="Approval Note",
        help="Optional note posted to the chatter of every approved quotation.",
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            vals["order_ids"] = [(6, 0, active_ids)]
        return vals

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("eh_log_base.group_eh_log_manager"):
            raise UserError(_(
                "[EHL-APPROVAL-010] Only logistics managers may run "
                "mass-approve."
            ))
        approved = self.env["sale.order"]
        for order in self.order_ids:
            if not order.eh_log_requires_approval:
                continue
            if order.eh_log_approved_by_id:
                continue
            order.action_eh_log_approve()
            if self.note:
                order.message_post(body=self.note)
            approved |= order
        title = _("Mass-approve complete")
        message = _("%(count)d quotation(s) approved.") % {
            "count": len(approved)
        }
        return self.env["sale.order"]._notify_success(title, message)


class EhLogQuotationMassCancel(models.TransientModel):
    _name = "eh.log.quotation.mass.cancel"
    _description = "Mass-cancel Logistics Quotations"

    order_ids = fields.Many2many(
        "sale.order",
        string="Quotations",
        required=True,
    )
    reason = fields.Text(
        string="Cancellation Reason",
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            vals["order_ids"] = [(6, 0, active_ids)]
        return vals

    def action_apply(self):
        self.ensure_one()
        cancelled = self.env["sale.order"]
        for order in self.order_ids:
            if order.state == "cancel":
                continue
            order._action_cancel()
            order.message_post(body=_(
                "Cancelled (mass action). Reason: %(reason)s"
            ) % {"reason": self.reason})
            cancelled |= order
        title = _("Mass-cancel complete")
        message = _("%(count)d quotation(s) cancelled.") % {
            "count": len(cancelled)
        }
        return self.env["sale.order"]._notify_success(title, message)


class EhLogQuotationMassSendReview(models.TransientModel):
    _name = "eh.log.quotation.mass.send.review"
    _description = "Mass-send Logistics Quotations for Review"

    order_ids = fields.Many2many(
        "sale.order",
        string="Quotations",
        required=True,
    )
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewer",
        required=True,
        default=lambda self: self.env.user,
    )
    deadline = fields.Date(
        string="Deadline",
        default=fields.Date.context_today,
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            vals["order_ids"] = [(6, 0, active_ids)]
        return vals

    def action_apply(self):
        self.ensure_one()
        nudged = self.env["sale.order"]
        for order in self.order_ids:
            order._nudge(
                summary=_("Quotation %s pending review") % order.name,
                user=self.reviewer_id,
                deadline=self.deadline,
            )
            nudged |= order
        title = _("Review nudges sent")
        message = _("%(count)d quotation(s) assigned to %(user)s.") % {
            "count": len(nudged),
            "user": self.reviewer_id.display_name,
        }
        return self.env["sale.order"]._notify_success(title, message)
