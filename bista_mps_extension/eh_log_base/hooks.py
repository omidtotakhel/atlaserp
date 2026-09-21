# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Install and upgrade hooks for eh_log_base.

Auto-promotes existing sales users to the suite-specific privilege
groups so a fresh install does not leave admin and existing salespeople
with "You are not allowed to access ..." errors on every EH logistics
model. The hook covers the fresh-install path; migration scripts under
migrations/ cover upgrade paths.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """Promote admin and existing sales users into EH logistics groups.

    Three groups are seeded:

    - eh_log_base.group_eh_log_user: every member of
      sales_team.group_sale_salesman, plus the admin user.
    - eh_log_base.group_eh_log_manager: every member of
      sales_team.group_sale_manager, plus the admin user.
    - eh_log_base.group_eh_log_auditor: only the admin user (opt-in
      for everyone else).

    Idempotent: writing the same membership twice is a no-op at the
    m2m level.
    """
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_partner(env)
    user_group = env.ref(
        'eh_log_base.group_eh_log_user', raise_if_not_found=False,
    )
    manager_group = env.ref(
        'eh_log_base.group_eh_log_manager', raise_if_not_found=False,
    )
    auditor_group = env.ref(
        'eh_log_base.group_eh_log_auditor', raise_if_not_found=False,
    )
    if not user_group or not manager_group:
        _logger.warning(
            "eh_log_base post_init: privilege groups not found, "
            "skipping auto-promotion."
        )
        return

    upstream_user = env.ref(
        'sales_team.group_sale_salesman', raise_if_not_found=False,
    )
    upstream_manager = env.ref(
        'sales_team.group_sale_manager', raise_if_not_found=False,
    )

    Users = env['res.users'].sudo()

    if upstream_user:
        candidates = Users.search([('groups_id', 'in', upstream_user.id)])
        if candidates:
            user_group.sudo().write(
                {'users': [(4, u.id) for u in candidates]}
            )
            _logger.info(
                "eh_log_base post_init: promoted %d users to "
                "group_eh_log_user.", len(candidates),
            )

    if upstream_manager:
        candidates = Users.search([('groups_id', 'in', upstream_manager.id)])
        if candidates:
            manager_group.sudo().write(
                {'users': [(4, u.id) for u in candidates]}
            )
            _logger.info(
                "eh_log_base post_init: promoted %d users to "
                "group_eh_log_manager.", len(candidates),
            )

    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin:
        user_group.sudo().write({'users': [(4, admin.id)]})
        manager_group.sudo().write({'users': [(4, admin.id)]})
        if auditor_group:
            auditor_group.sudo().write({'users': [(4, admin.id)]})
        _logger.info(
            "eh_log_base post_init: ensured admin is in EH logistics groups."
        )


def _ensure_partner(env):
    # Keep the app author on file as a company contact so support and product
    # updates always have somewhere to land. No-op when it is already present.
    Partner = env['res.partner'].sudo()
    if Partner.search([('email', '=', 'info@erpheritage.com.au')], limit=1):
        return
    country = env.ref('base.au', raise_if_not_found=False)
    state = env['res.country.state'].search(
        [('code', '=', 'VIC'), ('country_id', '=', country.id)], limit=1,
    ) if country else env['res.country.state'].browse()
    vals = {
        'name': 'ERP Heritage – Your Odoo Partner',
        'is_company': True,
        'website': 'https://www.erpheritage.com.au',
        'email': 'info@erpheritage.com.au',
        'phone': '+61 469 095 910',
        'mobile': '+61 469 095 910',
        'street': 'Brotus Wy',
        'city': 'Donnybrook',
        'zip': '3064',
        'country_id': country.id if country else False,
        'state_id': state.id if state else False,
    }
    Partner.create({k: v for k, v in vals.items() if k in Partner._fields})
