# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
{
    'name': 'Freight Forwarding',
    'summary': 'Freight Forwarding gives Odoo 16 Community a real forwarding job file for sea, air, road, rail, and multimodal moves, born from a confirmed Logistics Quotation and advanced through a state machine that blocks illegal jumps. freight forwarder, freight forwarding software, sea freight, air freight, ocean freight, NVOCC, house bill of lading, HBL, MBL, HAWB, MAWB, container tracking, ISO 6346, shipment milestones, job cost sheet, gross margin, multimodal, import export, 3PL, Odoo 16 logistics.',
    'description': 'A forwarding job spine for Odoo 16 Community. Confirm a logistics sale order and the module spawns a structured freight job carrying shipper, consignee, notify party, lane, Incoterm, milestone timeline, bills of lading, containers, and a cost and revenue ledger with live gross margin. State transitions are gated, container numbers are check-digit validated, and every job gets its own analytic account.',
    'author': 'ERP Heritage',
    'website': 'https://www.erpheritage.com.au/',
    'license': 'LGPL-3',
    'category': 'Inventory/Delivery',
    'version': '16.0.1.0.0',
    'depends': [
        'eh_log_base',
        'eh_log_quotation',
        'sale_management',
        'account',
        'purchase',
    ],
    'data': [
        'security/eh_log_freight_security.xml',
        'security/eh_log_freight_isolation_rules.xml',
        'security/ir.model.access.csv',
        'data/eh_log_freight_sequences.xml',
        'data/eh_log_freight_milestone_data.xml',
        'data/eh_log_freight_container_iso_data.xml',
        'report/eh_log_freight_job_report.xml',
        'views/eh_log_freight_job_views.xml',
        'views/eh_log_freight_job_kanban_calendar_pivot_graph_views.xml',
        'views/eh_log_freight_job_search_views.xml',
        'views/eh_log_freight_bl_views.xml',
        'views/eh_log_freight_container_views.xml',
        'views/sale_order_views.xml',
        'wizards/eh_log_freight_mass_action_views.xml',
        'views/eh_log_freight_menus.xml',
    ],
    'demo': ['demo/eh_log_demo_freight.xml'],
    'images': ['static/description/banner.gif'],
    'assets': {
        'web.assets_backend': ['eh_log_freight/static/src/js/eh_log_freight_tour.js'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
