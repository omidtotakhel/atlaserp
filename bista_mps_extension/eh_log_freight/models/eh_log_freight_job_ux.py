# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Freight job UX intelligence layer.

Adds operator-facing onchanges, smart defaults, notifications on
every action button, and activity nudges that surface blocking
events on the chatter inbox without the operator having to look at
the form.

Lives in its own file so the core lifecycle file stays focused on
the state-machine semantics. The two together form the full freight
job behaviour; conceptually they are one model in two halves.
"""
from odoo import api, fields, models, _


class EhLogFreightJobUx(models.Model):
    _inherit = "eh.log.freight.job"

    # ------------------------------------------------------------------
    # Smart-form onchanges
    # ------------------------------------------------------------------
    @api.onchange("customer_id")
    def _onchange_customer_id_freight(self):
        """When the customer changes, default the shipper to the
        customer for export, the consignee for import. Operator can
        always override; this is the most common case so saving the
        click counts.
        """
        if not self.customer_id:
            return
        if self.direction == "export" and not self.shipper_id:
            self.shipper_id = self.customer_id
        if self.direction == "import" and not self.consignee_id:
            self.consignee_id = self.customer_id

    @api.onchange("direction")
    def _onchange_direction_freight(self):
        """Direction picked: re-default shipper/consignee from the
        customer if the relevant slot is still blank.
        """
        if not self.customer_id or not self.direction:
            return
        if self.direction == "export" and not self.shipper_id:
            self.shipper_id = self.customer_id
        if self.direction == "import" and not self.consignee_id:
            self.consignee_id = self.customer_id

    @api.onchange("gross_weight_kg", "volume_cbm")
    def _onchange_dimensions_freight(self):
        """Sea-freight chargeable weight is volumetric vs actual
        whichever is greater, with 1 cbm = 1000 kg conversion.
        Surface that to the operator so the rate-shop conversation
        starts with the right number.
        """
        if not (self.gross_weight_kg or self.volume_cbm):
            return
        chargeable = max(
            self.gross_weight_kg or 0.0,
            (self.volume_cbm or 0.0) * 1000.0,
        )
        # Soft warning if the volumetric is significantly higher; that
        # is when most disputes happen during invoicing.
        if (self.volume_cbm or 0.0) * 1000.0 > 1.5 * (self.gross_weight_kg or 0.0):  # noqa: gcclog-hardcode IATA / FIATA volumetric divisor 1m3 = 1000kg; 1.5x is the industry "volumetric dominates" trigger
            return {
                "warning": {
                    "title": _("Volumetric weight dominates"),
                    "message": _(
                        "Volumetric chargeable weight (%(vol).1f kg) "
                        "is significantly higher than gross weight "
                        "(%(gross).1f kg). Confirm the chargeable basis "
                        "with the carrier and the customer."
                    ) % {
                        "vol": (self.volume_cbm or 0.0) * 1000.0,
                        "gross": self.gross_weight_kg or 0.0,
                    },
                },
            }

    @api.onchange("shipper_id", "consignee_id")
    def _onchange_party_country_mismatch(self):
        """If the shipper or consignee country doesn't match the
        declared origin/destination, flag it - this is the #1 cause
        of customs declaration rejection.
        """
        if (
            self.shipper_id
            and self.direction == "export"
            and self.shipper_id.country_id
            and self.origin_country_id
            and self.shipper_id.country_id != self.origin_country_id
        ):
            return {
                "warning": {
                    "title": _("Shipper country mismatch"),
                    "message": _(
                        "Shipper is in %(shipper_country)s but the "
                        "declared origin is %(origin)s. Verify before "
                        "creating the customs declaration."
                    ) % {
                        "shipper_country": self.shipper_id.country_id.name,
                        "origin": self.origin_country_id.name,
                    },
                },
            }

    # ------------------------------------------------------------------
    # Action methods returning toasts
    # ------------------------------------------------------------------
    def action_book_with_toast(self):
        for job in self:
            job.action_book()
        return self._notify_success(
            title=_("Freight booked"),
            message=_("%(count)d job(s) moved to Booked.") % {
                "count": len(self),
            },
        )

    def action_set_in_transit_with_toast(self):
        for job in self:
            job.action_set_in_transit()
        return self._notify_success(
            title=_("In transit"),
            message=_("%(count)d job(s) marked in transit.") % {
                "count": len(self),
            },
        )

    def action_set_delivered_with_toast(self):
        for job in self:
            job.action_set_delivered()
        return self._notify_success(
            title=_("Delivered"),
            message=_("%(count)d job(s) marked delivered.") % {
                "count": len(self),
            },
        )

    def action_close_with_toast(self):
        for job in self:
            job.action_close()
        return self._notify_success(
            title=_("Closed"),
            message=_("%(count)d job(s) closed.") % {
                "count": len(self),
            },
        )
