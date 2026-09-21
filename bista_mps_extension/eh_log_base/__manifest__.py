# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
{
    'name': 'Logistics Suite Base',
    'summary': 'Shared engine for the ERP Heritage logistics suite on Odoo 16 Community, a typed external-integration adapter framework with circuit breaker and mock-mode playback, an environment-and-encrypted-parameter credentials helper, a stable-coded exception hierarchy, an append-only operational audit log, and seeded freight charge-code and trade-document master data. Logistics, freight forwarding, customs broker integration framework, transport management TMS engine, EDI adapter, sea freight, air freight, road freight, multimodal, supply chain, Odoo 16 Community logistics base.',
    'description': 'Foundation module for the ERP Heritage logistics suite on Odoo 16 Community. Ships the shared adapter framework, credentials helper, typed exception hierarchy, append-only audit log, charge-code and document-type master data, a UX mixin, multi-company isolation rules, and a branded report shell. It is the engine the freight forwarding, customs, quotation, and road transport modules depend on, not an operational module on its own.',
    'author': 'ERP Heritage',
    'website': 'https://www.erpheritage.com.au/',
    'license': 'LGPL-3',
    'category': 'Inventory/Delivery',
    'version': '16.0.1.0.0',
    'depends': [
        'base',
        'mail',
        'sale_management',
        'account',
    ],
    'data': [
        'security/eh_log_security.xml',
        'security/eh_log_isolation_rules.xml',
        'security/ir.model.access.csv',
        'data/eh_log_paperformat.xml',
        'data/eh_log_ir_config_parameter.xml',
        'data/eh_log_sequences.xml',
        'data/eh_log_charge_code_data.xml',
        'data/eh_log_document_type_data.xml',
        'report/eh_log_report_base.xml',
        'views/eh_log_adapter_profile_views.xml',
        'views/eh_log_adapter_message_views.xml',
        'views/eh_log_event_views.xml',
        'views/eh_log_charge_code_views.xml',
        'views/eh_log_document_type_views.xml',
        'views/res_config_settings_views.xml',
        'views/eh_log_menus.xml',
    ],
    'demo': ['demo/eh_log_demo_partners.xml'],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'post_load': 'post_load_hook',
}
