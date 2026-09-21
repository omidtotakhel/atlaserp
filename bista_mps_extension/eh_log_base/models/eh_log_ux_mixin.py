# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Shared UX helpers: toast notifications, activity nudges, mass-action.

The mixin is inherited by every operational model that wants to fire
notifications on action methods, schedule activities on blocking
events, and expose a consistent "say something to the user" surface
so the operator never wonders what just happened.

Three helpers:

* ``_notify(title, message, kind, sticky=False)`` - returns the
  ``ir.actions.client`` dict that fires a toast in the web client.
  Action methods return the result of this helper so the toast
  appears the moment the button click resolves.

* ``_nudge(summary, user=None, deadline=None, kind='warning')`` -
  schedules a ``mail.activity`` on the record so the responsible
  operator sees a follow-up. Default user is the create-uid of the
  record; default deadline is today.

* ``_log_state_change(from_state, to_state, summary=None)`` - posts
  a chatter message with a coloured state-change line so the audit
  trail tells the story without the operator having to inspect the
  state field.
"""
from odoo import fields, models, _


# Notification kinds the helper accepts. Mapped to the toast colours
# the web client renders. Closed list because the renderer only
# knows these four; any other value is silently downgraded to info.
NOTIFICATION_KINDS = ("success", "info", "warning", "danger")


class EhLogUxMixin(models.AbstractModel):
    _name = "eh.log.ux.mixin"
    _description = "ERP Heritage UX Mixin"

    # ------------------------------------------------------------------
    # Toast notifications
    # ------------------------------------------------------------------
    def _notify(self, title, message=None, kind="success", sticky=False, next_action=None):
        """Return the ir.actions.client toast envelope.

        Action methods return this so the web client renders the
        toast immediately on click resolve. Pair with ``next_action``
        to chain to a different view after dismiss.
        """
        if kind not in NOTIFICATION_KINDS:
            kind = "info"
        params = {
            "title": title or "",
            "message": message or "",
            "type": kind,
            "sticky": bool(sticky),
        }
        if next_action:
            params["next"] = next_action
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    def _notify_success(self, title, message=None, next_action=None):
        return self._notify(title, message, kind="success", next_action=next_action)

    def _notify_warning(self, title, message=None):
        return self._notify(title, message, kind="warning", sticky=True)

    def _notify_danger(self, title, message=None):
        return self._notify(title, message, kind="danger", sticky=True)

    # ------------------------------------------------------------------
    # Activity nudges
    # ------------------------------------------------------------------
    def _nudge(self, summary, note=None, user=None, deadline=None, activity_type=None):
        """Schedule a follow-up activity on the record.

        The default activity type is the standard 'warning' (yellow
        triangle); operators can override with a specific type when
        they want a different colour or icon.
        """
        for record in self:
            target_user = (
                user
                or (record.create_uid if "create_uid" in record._fields else False)
                or self.env.user
            )
            target_deadline = deadline or fields.Date.context_today(record)
            type_xmlid = activity_type or "mail.mail_activity_data_warning"
            record.activity_schedule(
                type_xmlid,
                summary=summary,
                note=note or "",
                user_id=target_user.id if target_user else self.env.uid,
                date_deadline=target_deadline,
            )

    # ------------------------------------------------------------------
    # State-change chatter
    # ------------------------------------------------------------------
    def _log_state_change(self, from_state, to_state, summary=None):
        """Post a chatter line announcing the transition.

        Used by every operational state machine so the chatter timeline
        carries a coloured "Draft -> Booked" line per transition,
        independent of the field tracking that already exists.
        """
        for record in self:
            label = summary or _(
                "State changed: %(from)s -> %(to)s"
            ) % {"from": from_state or "_", "to": to_state or "_"}
            record.message_post(body=label)

    # ------------------------------------------------------------------
    # Generic open-form helper (for mass actions)
    # ------------------------------------------------------------------
    def action_open_form(self):
        """Return an act_window opening the form view for self."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }
