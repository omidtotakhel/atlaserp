```python
# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MrpProductionSchedule(models.Model):
    """
    Inherit the native MPS model to add a smart button that opens the
    vendor demand analysis filtered on the current schedule line.
    """

    _inherit = 'mrp.production.schedule'

    vendor_demand_count = fields.Integer(
        string='Vendor Demand Rows',
        compute='_compute_vendor_demand_count',
    )

    @api.depends('product_id')
    def _compute_vendor_demand_count(self):
        """
        Count distinct (vendor, period) combinations for each schedule.
        We query the SQL view through the ORM to stay cache-friendly.
        """
        for rec in self:
            rec.vendor_demand_count = self.env['mps.vendor.demand'].search_count(
                [('schedule_id', '=', rec.id)]
            )

    def action_view_vendor_demand(self):
        """
        Smart-button action: open the MPS Vendor Demand analysis
        filtered on this particular MPS line.
        """
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'mrp_mps_vendor_demand.action_mps_vendor_demand'
        )
        action['domain'] = [('schedule_id', '=', self.id)]
        action['context'] = dict(
            self.env.context,
            search_default_schedule_id=self.id,
        )
        return action
```