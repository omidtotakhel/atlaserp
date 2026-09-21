```python
# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MpsVendorDemandWizard(models.TransientModel):
    """
    Lightweight wizard that lets the user filter the Vendor Demand
    report by date range and/or specific products / vendors before
    opening the analysis view.
    """

    _name = 'mps.vendor.demand.wizard'
    _description = 'MPS Vendor Demand Wizard'

    date_from = fields.Date(
        string='From Period',
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string='To Period',
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Products',
        domain=[('purchase_ok', '=', True)],
        help='Leave empty to include all purchased products.',
    )
    vendor_ids = fields.Many2many(
        'res.partner',
        string='Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Leave empty to include all vendors.',
    )
    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        string='Warehouses',
        help='Leave empty to include all warehouses.',
    )
    group_by = fields.Selection(
        selection=[
            ('vendor_id', 'Vendor'),
            ('product_id', 'Product'),
            ('date_start', 'Period'),
            ('warehouse_id', 'Warehouse'),
        ],
        string='Group By',
        default='vendor_id',
    )

    # ------------------------------------------------------------------ #

    def action_open_report(self):
        self.ensure_one()
        domain = []
        if self.date_from:
            domain.append(('date_start', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_stop', '<=', self.date_to))
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        if self.vendor_ids:
            domain.append(('vendor_id', 'in', self.vendor_ids.ids))
        if self.warehouse_ids:
            domain.append(('warehouse_id', 'in', self.warehouse_ids.ids))

        ctx = dict(self.env.context)
        if self.group_by:
            ctx['search_default_%s' % self.group_by] = 1

        action = self.env['ir.actions.act_window']._for_xml_id(
            'mrp_mps_vendor_demand.action_mps_vendor_demand'
        )
        action['domain'] = domain
        action['context'] = ctx
        return action
```