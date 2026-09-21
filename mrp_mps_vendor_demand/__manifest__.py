```python
{
    'name': 'MPS Vendor Demand',
    'version': '16.0.1.0.0',
    'summary': 'Extend MPS to show product demand grouped by vendor',
    'description': """
Extends the Master Production Schedule (MPS) to provide a dedicated report
showing how the forecasted replenishment quantities for purchased products are
distributed across applicable vendors (product.supplierinfo).

Features
--------
* New **MPS → Vendor Demand** menu entry.
* Pivot, Graph, and List views on the mps.vendor.demand analysis model.
* Optional wizard to filter by date range, product, vendor, or warehouse
  before opening the report.
* Smart button on MPS form lines that jumps directly to the filtered
  vendor demand for that product.
* Demand is derived from the MPS "To Replenish" quantities per period and
  is broken down per vendor using each product's active vendor pricelist.
    """,
    'author': 'Custom',
    'category': 'Manufacturing',
    'license': 'LGPL-3',
    'depends': [
        'mrp_mps',
        'purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/mps_vendor_demand_views.xml',
        'views/mrp_production_schedule_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mrp_mps_vendor_demand/static/src/scss/mps_vendor_demand.scss',
            'mrp_mps_vendor_demand/static/src/xml/mps_vendor_demand.xml',
            'mrp_mps_vendor_demand/static/src/js/mps_vendor_demand_action.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
```