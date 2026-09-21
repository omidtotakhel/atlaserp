# -*- coding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
{
    'name': 'MPS Vendor Demand Report',
    'summary': (
        'Extends Master Production Schedule (MPS) visibility by grouping '
        'procurement demand by vendor. Purchased products are matched against '
        'their product.supplierinfo records and active draft/sent purchase '
        'orders so purchasing and planning teams can see upcoming vendor '
        'demand directly from within the Logistics suite. Provides a '
        'filterable list view and a branded PDF report grouped by vendor.'
    ),
    'description': (
        'For every reordering rule that drives a Buy route, this module '
        'resolves the applicable vendors from product.supplierinfo and '
        'surfaces the demand quantity together with any in-progress purchase '
        'order lines. The data is presented in a wizard-driven list view '
        '(filterable by warehouse, company, date horizon) and a printable '
        'A4 Landscape PDF using the ERP Heritage Logistics design system.'
    ),
    'author': 'ERP Heritage',
    'website': 'https://www.erpheritage.com.au/',
    'license': 'LGPL-3',
    'category': 'Inventory/Purchase',
    'version': '16.0.1.0.0',
    'depends': [
        'eh_log_base',
        'purchase',
        'purchase_stock',
        'stock',
        'mrp_mps',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/mps_vendor_demand_report.xml',
        'wizards/mps_vendor_demand_wizard_views.xml',
        'views/mps_vendor_demand_views.xml',
        'views/mps_vendor_demand_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}