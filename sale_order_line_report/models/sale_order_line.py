# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    """
    Thin extension of sale.order.line – no new stored fields are needed.
    The class exists only to register the server-side action used by the
    "Open Order" row-level shortcut.
    """

    _inherit = 'sale.order.line'

    def action_open_sale_order(self):
        """Open the parent sale order form view from a sale order line record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.order_id.id,
        }