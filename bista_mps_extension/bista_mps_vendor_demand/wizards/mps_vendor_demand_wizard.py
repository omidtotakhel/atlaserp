# -*- coding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
mps_vendor_demand_wizard  –  driver wizard for the MPS Vendor Demand report
=============================================================================

The wizard collects filter parameters (company, warehouses, date horizon),
runs ``_build_demand_lines`` to populate ``mps.vendor.demand.line`` records
linked to this wizard session, then either:
  * opens the list view of those records, or
  * renders the PDF via ir.actions.report.

Algorithm (``_build_demand_lines``)
-------------------------------------
1. Collect all active reordering rules that have a Buy route or at least one
   supplier configured within the selected warehouses / company.
2. For each orderpoint product, gather product.supplierinfo records that are
   valid for today (date_start / date_end) and whose company matches.
3. Compute demand_qty = max(orderpoint.qty_to_order, supplierinfo.min_qty).
4. Look up existing draft/sent purchase.order.line records grouped by
   (product, commercial_partner) to fill po_qty_draft / open_po_count.
5. Confirmed-state PO lines are aggregated for po_qty_confirmed.
6. Create mps.vendor.demand.line records in bulk.
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MpsVendorDemandWizard(models.TransientModel):
    _name = 'mps.vendor.demand.wizard'
    _description = 'MPS Vendor Demand – Report Wizard'

    # ------------------------------------------------------------------ #
    # Filter parameters                                                    #
    # ------------------------------------------------------------------ #

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        string='Warehouses',
        domain="[('company_id', '=', company_id)]",
        help='Leave empty to include all warehouses of the selected company.',
    )
    date_horizon = fields.Integer(
        string='Planning Horizon (days)',
        default=90,
        required=True,
        help=(
            'Number of calendar days from today to include in the report. '
            'Reordering rules whose lead_days_date falls within this window '
            'are included. Set to 0 to include all rules regardless of date.'
        ),
    )
    include_zero_demand = fields.Boolean(
        string='Include Zero-Demand Lines',
        default=False,
        help=(
            'When checked, vendor lines where qty_to_order = 0 are still '
            'shown so planners can review full vendor coverage.'
        ),
    )
    only_uncovered = fields.Boolean(
        string='Only Uncovered Demand',
        default=False,
        help='Show only lines where draft PO quantity does not fully cover demand.',
    )

    # ------------------------------------------------------------------ #
    # Result link                                                          #
    # ------------------------------------------------------------------ #

    line_ids = fields.One2many(
        'mps.vendor.demand.line',
        'wizard_id',
        string='Demand Lines',
        readonly=True,
    )
    line_count = fields.Integer(
        string='Lines Generated',
        compute='_compute_line_count',
    )

    @api.depends('line_ids')
    def _compute_line_count(self):
        for wiz in self:
            wiz.line_count = len(wiz.line_ids)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _get_buy_action_route_ids(self):
        """Return ids of stock.route records that include at least one 'buy' rule."""
        buy_rules = self.env['stock.rule'].sudo().search([('action', '=', 'buy')])
        return buy_rules.mapped('route_id').ids

    def _get_orderpoints(self):
        """Return in-scope reordering rules filtered to Buy-route products."""
        self.ensure_one()
        buy_route_ids = self._get_buy_action_route_ids()

        domain = [
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ]
        if self.warehouse_ids:
            domain.append(('warehouse_id', 'in', self.warehouse_ids.ids))
        else:
            wh = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id),
            ])
            domain.append(('warehouse_id', 'in', wh.ids))

        if self.date_horizon > 0:
            horizon_limit = date.today() + relativedelta(days=self.date_horizon)
            domain.append(('lead_days_date', '<=', horizon_limit))

        if not self.include_zero_demand:
            domain.append(('qty_to_order', '>', 0))

        orderpoints = self.env['stock.warehouse.orderpoint'].search(domain)

        # Restrict to orderpoints whose product has a Buy route or vendor(s)
        result = self.env['stock.warehouse.orderpoint']
        for op in orderpoints:
            if not op.product_id:
                continue
            product_route_ids = set(op.product_id.route_ids.ids)
            product_route_ids.update(
                op.product_id.product_tmpl_id.categ_id.total_route_ids.ids
            )
            if op.route_id:
                product_route_ids.add(op.route_id.id)
            has_buy_route = bool(
                buy_route_ids and product_route_ids.intersection(buy_route_ids)
            )
            has_sellers = bool(op.product_id.seller_ids)
            if has_buy_route or has_sellers:
                result |= op
        return result

    def _get_po_lines_by_product_partner(self, product_ids, company_id):
        """
        Return:
          draft_lines  : {(product_id, commercial_partner_id): {'qty': float, 'po_ids': set}}
          confirm_lines: {product_id: float}
        """
        PurchaseLine = self.env['purchase.order.line'].sudo()

        draft_domain = [
            ('product_id', 'in', product_ids),
            ('order_id.company_id', '=', company_id),
            ('order_id.state', 'in', ('draft', 'sent', 'to approve')),
            ('display_type', '=', False),
        ]
        draft_lines = {}
        for pol in PurchaseLine.search(draft_domain):
            partner = pol.partner_id
            cp_id = (partner.commercial_partner_id or partner).id
            key = (pol.product_id.id, cp_id)
            if key not in draft_lines:
                draft_lines[key] = {'qty': 0.0, 'po_ids': set()}
            draft_lines[key]['qty'] += pol.product_qty
            draft_lines[key]['po_ids'].add(pol.order_id.id)

        confirmed_domain = [
            ('product_id', 'in', product_ids),
            ('order_id.company_id', '=', company_id),
            ('order_id.state', 'in', ('purchase', 'done')),
            ('display_type', '=', False),
        ]
        confirm_lines = {}
        for pol in PurchaseLine.search(confirmed_domain):
            pid = pol.product_id.id
            confirm_lines[pid] = confirm_lines.get(pid, 0.0) + pol.product_qty

        return draft_lines, confirm_lines

    # ------------------------------------------------------------------ #
    # Core build logic                                                    #
    # ------------------------------------------------------------------ #

    def _build_demand_lines(self):
        """
        Resolve orderpoints → vendors → PO coverage, then bulk-create
        mps.vendor.demand.line records linked to this wizard session.
        """
        self.ensure_one()

        # Remove previously generated lines for this session
        self.line_ids.unlink()

        orderpoints = self._get_orderpoints()
        if not orderpoints:
            return

        product_ids = list({op.product_id.id for op in orderpoints if op.product_id})
        today = date.today()

        draft_lines, confirm_lines = self._get_po_lines_by_product_partner(
            product_ids, self.company_id.id
        )

        # Fetch valid supplierinfo for all relevant templates
        tmpl_ids = list({
            op.product_id.product_tmpl_id.id
            for op in orderpoints
            if op.product_id
        })
        seller_domain = [
            ('product_tmpl_id', 'in', tmpl_ids),
            '|',
                ('company_id', '=', False),
                ('company_id', '=', self.company_id.id),
            '|',
                ('date_start', '=', False),
                ('date_start', '<=', fields.Date.today()),
            '|',
                ('date_end', '=', False),
                ('date_end', '>=', fields.Date.today()),
        ]
        all_sellers = self.env['product.supplierinfo'].sudo().search(
            seller_domain, order='product_tmpl_id, sequence'
        )

        sellers_by_tmpl = {}
        for si in all_sellers:
            sellers_by_tmpl.setdefault(si.product_tmpl_id.id, []).append(si)

        vals_list = []

        for op in orderpoints:
            product = op.product_id
            if not product:
                continue

            tmpl_id = product.product_tmpl_id.id
            sellers = sellers_by_tmpl.get(tmpl_id, [])
            raw_to_order = op.qty_to_order or 0.0

            # ── No vendor configured: placeholder line ─────────────── #
            if not sellers:
                demand_qty = raw_to_order
                if not self.include_zero_demand and demand_qty <= 0:
                    continue
                if self.only_uncovered and demand_qty <= 0:
                    continue
                vals_list.append({
                    'wizard_id': self.id,
                    'company_id': self.company_id.id,
                    'warehouse_id': op.warehouse_id.id,
                    'product_id': product.id,
                    'product_uom_id': op.product_uom.id,
                    'vendor_id': False,
                    'vendor_sequence': 0,
                    'vendor_product_name': False,
                    'vendor_product_code': False,
                    'vendor_lead_time': 0,
                    'vendor_min_qty': 0.0,
                    'vendor_price': 0.0,
                    'vendor_currency_id': self.company_id.currency_id.id,
                    'orderpoint_id': op.id,
                    'orderpoint_qty_to_order': raw_to_order,
                    'qty_on_hand': op.qty_on_hand or 0.0,
                    'qty_forecast': op.qty_forecast or 0.0,
                    'demand_qty': demand_qty,
                    'po_qty_draft': 0.0,
                    'po_qty_confirmed': 0.0,
                    'open_po_count': 0,
                    'horizon_date': today,
                })
                continue

            # ── One line per vendor ────────────────────────────────── #
            for si in sellers:
                partner = si.partner_id
                cp = partner.commercial_partner_id or partner
                cp_id = cp.id

                demand_qty = max(raw_to_order, si.min_qty or 0.0)

                if not self.include_zero_demand and demand_qty <= 0:
                    continue

                po_key = (product.id, cp_id)
                draft_data = draft_lines.get(po_key, {})
                po_draft_qty = draft_data.get('qty', 0.0)
                open_po_count = len(draft_data.get('po_ids', set()))
                po_confirmed_qty = confirm_lines.get(product.id, 0.0)

                if self.only_uncovered:
                    if po_draft_qty + po_confirmed_qty >= demand_qty:
                        continue

                horizon = today + relativedelta(days=int(si.delay or 0))

                vals_list.append({
                    'wizard_id': self.id,
                    'company_id': self.company_id.id,
                    'warehouse_id': op.warehouse_id.id,
                    'product_id': product.id,
                    'product_uom_id': op.product_uom.id,
                    'vendor_id': si.partner_id.id,
                    'vendor_sequence': si.sequence or 1,
                    'vendor_product_name': si.product_name or False,
                    'vendor_product_code': si.product_code or False,
                    'vendor_lead_time': int(si.delay or 0),
                    'vendor_min_qty': si.min_qty or 0.0,
                    'vendor_price': si.price or 0.0,
                    'vendor_currency_id': (
                        si.currency_id.id
                        if si.currency_id
                        else self.company_id.currency_id.id
                    ),
                    'orderpoint_id': op.id,
                    'orderpoint_qty_to_order': raw_to_order,
                    'qty_on_hand': op.qty_on_hand or 0.0,
                    'qty_forecast': op.qty_forecast or 0.0,
                    'demand_qty': demand_qty,
                    'po_qty_draft': po_draft_qty,
                    'po_qty_confirmed': po_confirmed_qty,
                    'open_po_count': open_po_count,
                    'horizon_date': horizon,
                })

        if vals_list:
            self.env['mps.vendor.demand.line'].sudo().create(vals_list)

    # ------------------------------------------------------------------ #
    # Button actions                                                       #
    # ------------------------------------------------------------------ #

    def action_generate(self):
        """Regenerate demand lines then reload the wizard form."""
        self.ensure_one()
        self._build_demand_lines()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mps.vendor.demand.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_view_lines(self):
        """Open the generated demand lines in a list view."""
        self.ensure_one()
        if not self.line_ids:
            self._build_demand_lines()
        if not self.line_ids:
            raise UserError(_(
                'No vendor demand lines were generated for the selected filters.\n\n'
                'Possible reasons:\n'
                '• Purchased products do not have vendor pricelists configured.\n'
                '• No reordering rules exist with a pending qty_to_order '
                '  (try enabling "Include Zero-Demand Lines").\n'
                '• No products have a Buy route or vendor pricelist within '
                '  the selected warehouses.'
            ))
        return {
            'name': _('MPS Vendor Demand'),
            'type': 'ir.actions.act_window',
            'res_model': 'mps.vendor.demand.line',
            'view_mode': 'list,form',
            'views': [
                (False, 'list'),
                (False, 'form'),
            ],
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'search_default_group_by_vendor': 1,
                'create': False,
                'edit': False,
                'delete': False,
            },
        }

    def action_print_report(self):
        """Generate lines (if not already done) then render the PDF report."""
        self.ensure_one()
        if not self.line_ids:
            self._build_demand_lines()
        if not self.line_ids:
            raise UserError(_(
                'No vendor demand lines were generated for the selected filters.\n\n'
                'Possible reasons:\n'
                '• Purchased products do not have vendor pricelists configured.\n'
                '• No reordering rules exist with a pending qty_to_order '
                '  (try enabling "Include Zero-Demand Lines").\n'
                '• No products have a Buy route or vendor pricelist within '
                '  the selected warehouses.'
            ))
        return self.env.ref(
            'bista_mps_vendor_demand.action_report_mps_vendor_demand'
        ).report_action(self)