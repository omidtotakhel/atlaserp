```python
# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
from odoo.tools import float_round


class MpsVendorDemand(models.Model):
    """
    Read-only analysis model that flattens MPS replenishment quantities
    per (product, vendor, period) into rows that can be explored through
    pivot / graph / list views.

    The records are stored in a plain SQL view (``_auto = False``) so
    they are always in sync with the underlying MPS data and vendor
    pricelist without any additional sync step.
    """

    _name = 'mps.vendor.demand'
    _description = 'MPS Vendor Demand Analysis'
    _auto = False
    _rec_name = 'product_id'
    _order = 'date_start, vendor_id, product_id'

    # ------------------------------------------------------------------ #
    #  Fields                                                              #
    # ------------------------------------------------------------------ #

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        readonly=True,
    )
    categ_id = fields.Many2one(
        'product.category',
        string='Product Category',
        readonly=True,
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        readonly=True,
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        readonly=True,
    )
    date_start = fields.Date(
        string='Period Start',
        readonly=True,
    )
    date_stop = fields.Date(
        string='Period End',
        readonly=True,
    )
    replenish_qty = fields.Float(
        string='Replenish Quantity',
        digits='Product Unit of Measure',
        readonly=True,
        help='Quantity to replenish in this period (from MPS "To Replenish").',
    )
    vendor_price = fields.Float(
        string='Vendor Price',
        digits='Product Price',
        readonly=True,
        help='Unit price from the vendor pricelist (in vendor currency).',
    )
    vendor_currency_id = fields.Many2one(
        'res.currency',
        string='Vendor Currency',
        readonly=True,
    )
    vendor_lead_time = fields.Float(
        string='Vendor Lead Time (days)',
        readonly=True,
    )
    vendor_min_qty = fields.Float(
        string='Vendor Min Qty',
        readonly=True,
    )
    priority = fields.Integer(
        string='Vendor Priority',
        readonly=True,
        help='Lower value = higher priority (sequence on vendor pricelist).',
    )
    schedule_id = fields.Many2one(
        'mrp.production.schedule',
        string='MPS Line',
        readonly=True,
    )

    # ------------------------------------------------------------------ #
    #  SQL View                                                            #
    # ------------------------------------------------------------------ #

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW mps_vendor_demand AS
            SELECT
                -- surrogate key: combine forecast slot id + supplier id
                ROW_NUMBER() OVER ()                            AS id,
                mps.id                                          AS schedule_id,
                mps.product_id                                  AS product_id,
                pt.id                                           AS product_tmpl_id,
                pt.categ_id                                     AS categ_id,
                mps.company_id                                  AS company_id,
                mps.warehouse_id                                AS warehouse_id,
                mps.product_uom_id                              AS uom_id,
                si.partner_id                                   AS vendor_id,
                si.currency_id                                  AS vendor_currency_id,
                COALESCE(si.price, 0.0)                         AS vendor_price,
                COALESCE(si.delay, 0.0)                         AS vendor_lead_time,
                COALESCE(si.min_qty, 0.0)                       AS vendor_min_qty,
                COALESCE(si.sequence, 1)                        AS priority,
                fs.date_start                                   AS date_start,
                fs.date_stop                                    AS date_stop,
                COALESCE(fs.replenish_qty, 0.0)                 AS replenish_qty
            FROM mrp_production_schedule           AS mps
            JOIN product_product                   AS pp  ON pp.id  = mps.product_id
            JOIN product_template                  AS pt  ON pt.id  = pp.product_tmpl_id
            -- only products that are purchased
            INNER JOIN product_supplierinfo        AS si
                ON  si.product_tmpl_id = pt.id
                AND (si.product_id IS NULL OR si.product_id = mps.product_id)
                AND (si.date_end   IS NULL OR si.date_end   >= CURRENT_DATE)
                AND (si.date_start IS NULL OR si.date_start <= CURRENT_DATE)
            -- cross with the MPS forecast slots (one row per period)
            INNER JOIN mrp_production_schedule_forecast AS fs
                ON  fs.production_schedule_id = mps.id
            WHERE
                fs.replenish_qty > 0
                AND pt.purchase_ok = TRUE
        """)

    # ------------------------------------------------------------------ #
    #  Helper actions                                                      #
    # ------------------------------------------------------------------ #

    def action_open_mps(self):
        """Navigate to the parent MPS line."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Master Production Schedule',
            'res_model': 'mrp.production.schedule',
            'view_mode': 'list,form',
            'domain': [('id', '=', self.schedule_id.id)],
        }

    def action_open_vendor(self):
        """Open vendor form."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': self.vendor_id.id,
        }
```