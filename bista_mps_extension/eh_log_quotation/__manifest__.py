# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
{
    'name': 'Logistics Quotation',
    'summary': 'Logistics-aware extension of the Odoo sale order that prices freight by charge code and leg, computes gross margin against planned cost in real time, checks live customer credit exposure against the approved limit, and gates confirmation behind a manager approval that is recorded to the chatter and the operational event log. Freight forwarding quotation, freight quote, charge template, rate bundle, margin guard, credit guard, KYC guard, sale order extension, multi-leg pricing, disbursement handling, preflight checklist, manager approval matrix, Odoo 16 Community logistics, 3PL, NVOCC, customs broker, sea air road rail multimodal.',
    'description': 'Extends sale.order for freight forwarders and 3PL operators. Every line carries a standardised charge code and a leg classification (origin, main, destination, inland, customs, insurance). Gross margin is computed live from line revenue versus planned cost with disbursements excluded, customer credit exposure is read from open receivables against the approved limit, and a configurable approval gate blocks confirmation until a manager signs off. Charge templates pre-fill quotations by lane and mode, a preflight wizard runs every guard in one pass, and approvals are written to the chatter and the operational event log. Multi-company throughout. The KYC guard plumbing is shipped here and evaluated by the dedicated Logistics KYC module.',
    'author': 'ERP Heritage',
    'website': 'https://www.erpheritage.com.au/',
    'license': 'LGPL-3',
    'category': 'Inventory/Delivery',
    'version': '16.0.1.0.0',
    'depends': [
        'eh_log_base',
        'sale_management',
        'sale_margin',
        'account',
    ],
    'data': [
        'security/eh_log_quotation_security.xml',
        'security/eh_log_quotation_isolation_rules.xml',
        'security/ir.model.access.csv',
        'data/eh_log_quotation_data.xml',
        'views/eh_log_charge_template_views.xml',
        'views/sale_order_views.xml',
        'views/eh_log_quotation_kanban_views.xml',
        'views/eh_log_quotation_pivot_graph_calendar_views.xml',
        'wizards/eh_log_quotation_preflight_views.xml',
        'wizards/eh_log_charge_template_apply_views.xml',
        'wizards/eh_log_mass_action_wizards_views.xml',
        'views/eh_log_quotation_menus.xml',
    ],
    'demo': ['demo/eh_log_demo_charge_templates.xml', 'demo/eh_log_demo_quotations.xml'],
    'images': ['static/description/banner.gif'],
    'assets': {
        'web.assets_backend': ['eh_log_quotation/static/src/js/eh_log_quotation_tour.js'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
