# -*- coding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
mps_vendor_demand_line  –  persisted demand line linked to a wizard session
===========================================================================

Each record represents one (product × vendor) pairing derived from:
  - stock.warehouse.orderpoint  (reordering rule carrying a Buy route)
  - product.supplierinfo         (vendor pricelists on the product)
  - purchase.order.line          (draft / sent / confirmed PO lines)

Records are created in bulk by the wizard's ``_build_demand_lines`` method
and cascade-deleted when the wizard record is discarded.  They live long
enough for the list view and PDF renderer to consume them.

Field index
-----------
wizard_id                – parent TransientModel session (cascade delete)
company_id               – company owning the orderpoint
warehouse_id             – warehouse owning the orderpoint
product_id               – storable product
product_uom_id           – UoM used by the reordering rule
vendor_id                – res.partner of the matched supplier
vendor_sequence          – sequence from product.supplierinfo (priority order)
vendor_product_name      – vendor's own description
vendor_product_code      – vendor's own SKU code
vendor_lead_time         – delivery lead time in days
vendor_min_qty           – minimum order quantity from supplierinfo
vendor_price             – unit price from supplierinfo
vendor_currency_id       – currency of vendor_price
orderpoint_id            – originating reordering rule
orderpoint_qty_to_order  – qty_to_order on the orderpoint
qty_on_hand              – current on-hand quantity
qty_forecast             – forecasted quantity
demand_qty               – max(orderpoint_qty_to_order, vendor_min_qty)
po_qty_draft             – sum of draft/sent PO line quantities
po_qty_confirmed         – sum of confirmed PO line quantities
open_po_count            – number of distinct draft/sent POs
uncovered_qty            – demand_qty minus po_qty_draft (floored at 0)
horizon_date             – today + vendor lead time
"""

from odoo import _, api, fields, models


class MpsVendorDemandLine(models.Model):
    _name = 'mps.vendor.demand.line'
    _description = 'MPS Vendor Demand Line'
    _order = 'vendor_id, product_id, id'
    _check_company_auto = True

    # ------------------------------------------------------------------ #
    # Session link                                                         #
    # ------------------------------------------------------------------ #

    wizard_id = fields.Many2one(
        'mps.vendor.demand.wizard',
        string='Wizard Session',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Relational / grouping fields                                         #
    # ------------------------------------------------------------------ #

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        index=True,
        check_company=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        index=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        index=True,
    )
    orderpoint_id = fields.Many2one(
        'stock.warehouse.orderpoint',
        string='Reordering Rule',
        check_company=True,
    )

    # ------------------------------------------------------------------ #
    # Vendor info (from product.supplierinfo)                             #
    # ------------------------------------------------------------------ #

    vendor_sequence = fields.Integer(
        string='Vendor Priority',
        default=1,
        help='Lower number = higher priority (from product vendor pricelist).',
    )
    vendor_product_name = fields.Char(
        string='Vendor Product Name',
        help="Vendor's own description for this product.",
    )
    vendor_product_code = fields.Char(
        string='Vendor SKU',
        help="Vendor's own SKU / part number.",
    )
    vendor_lead_time = fields.Integer(
        string='Lead Time (days)',
        help='Vendor delivery lead time in calendar days.',
    )
    vendor_min_qty = fields.Float(
        string='Vendor Min Qty',
        digits='Product Unit of Measure',
        help='Minimum order quantity required by the vendor.',
    )
    vendor_price = fields.Float(
        string='Vendor Unit Price',
        digits='Product Price',
        help='Last known vendor unit price (from product vendor pricelist).',
    )
    vendor_currency_id = fields.Many2one(
        'res.currency',
        string='Vendor Currency',
    )

    # ------------------------------------------------------------------ #
    # Demand quantities                                                    #
    # ------------------------------------------------------------------ #

    orderpoint_qty_to_order = fields.Float(
        string='MPS To Order',
        digits='Product Unit of Measure',
        help='qty_to_order from the reordering rule (computed by MPS scheduler).',
    )
    qty_on_hand = fields.Float(
        string='On Hand',
        digits='Product Unit of Measure',
    )
    qty_forecast = fields.Float(
        string='Forecasted',
        digits='Product Unit of Measure',
    )
    demand_qty = fields.Float(
        string='Demand Qty',
        digits='Product Unit of Measure',
        help=(
            'Effective demand quantity: max(MPS To Order, Vendor Min Qty). '
            'Reflects the actual quantity that would be placed on a PO taking '
            'the vendor minimum order quantity into account.'
        ),
    )

    # ------------------------------------------------------------------ #
    # Purchase order coverage                                             #
    # ------------------------------------------------------------------ #

    po_qty_draft = fields.Float(
        string='Draft PO Qty',
        digits='Product Unit of Measure',
        help='Sum of product quantities on draft / sent / to-approve POs for this vendor.',
    )
    po_qty_confirmed = fields.Float(
        string='Confirmed PO Qty',
        digits='Product Unit of Measure',
        help='Sum of product quantities on confirmed (Purchase Order state) POs for this vendor.',
    )
    open_po_count = fields.Integer(
        string='Open POs',
        help='Number of distinct draft/sent purchase orders for this vendor + product.',
    )
    uncovered_qty = fields.Float(
        string='Uncovered Qty',
        digits='Product Unit of Measure',
        compute='_compute_uncovered_qty',
        store=True,
        help=(
            'Demand Qty minus Draft PO Qty (floored at 0). '
            'A positive value means demand is not yet covered by any open PO.'
        ),
    )

    # ------------------------------------------------------------------ #
    # Planning horizon                                                    #
    # ------------------------------------------------------------------ #

    horizon_date = fields.Date(
        string='Horizon Date',
        help='Estimated arrival date: today + vendor lead time.',
    )

    # ------------------------------------------------------------------ #
    # Computed fields                                                     #
    # ------------------------------------------------------------------ #

    @api.depends('demand_qty', 'po_qty_draft')
    def _compute_uncovered_qty(self):
        for line in self:
            line.uncovered_qty = max(
                0.0,
                (line.demand_qty or 0.0) - (line.po_qty_draft or 0.0)
            )

    # ------------------------------------------------------------------ #
    # Coverage status helpers (called from QWeb report template)          #
    # ------------------------------------------------------------------ #

    def _get_coverage_status(self):
        """Return a (label, css_class) tuple for display in the PDF report."""
        total_covered = (self.po_qty_draft or 0.0) + (self.po_qty_confirmed or 0.0)
        demand = self.demand_qty or 0.0
        draft_qty = self.po_qty_draft or 0.0

        if demand <= 0:
            return (_('No Demand'), 'eh_pdf_status_neutral')
        if total_covered >= demand:
            return (_('Covered'), 'eh_pdf_status_ok')
        if draft_qty > 0:
            return (_('Partial'), 'eh_pdf_status_warn')
        return (_('Uncovered'), 'eh_pdf_status_danger')

    def get_coverage_label(self):
        """Public helper called by the QWeb PDF template."""
        return self._get_coverage_status()[0]

    def get_coverage_css(self):
        """Public helper called by the QWeb PDF template."""
        return self._get_coverage_status()[1]