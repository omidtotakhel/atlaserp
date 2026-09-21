# -*- coding: utf-8 -*-
{
    'name': 'Sales Order Line Report',
    'version': '16.0.1.0.0',
    'summary': 'Dedicated Sales Order Lines menu under the Sales module for reporting',
    'description': """
Sales Order Line Report
=======================
Adds a dedicated **Sales Order Lines** menu entry under the Sales ▸ Reporting
section so that managers and salespeople can instantly browse, filter, group,
and analyse every individual sales order line across all orders.

Features
--------
* **List view** – see every line with order, customer, product, salesperson,
  quantities (ordered / delivered / invoiced / to-invoice), unit price,
  subtotal and invoice status.
* **Pivot view** – aggregate subtotals by any combination of dimensions
  (salesperson, customer, product, category, order date, state …).
* **Graph view** – bar / line / pie charts of subtotals or quantities.
* **Rich search panel** – filters for "To Invoice", "My Lines", state;
  group-by salesperson, customer, product, category, order date.
* Menu placed under the existing **Reporting** menu item in Sales so it
  sits alongside the standard *Sales Analysis* entry.
    """,
    'author': 'Custom',
    'category': 'Sales/Sales',
    'license': 'LGPL-3',
    'depends': [
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_line_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}