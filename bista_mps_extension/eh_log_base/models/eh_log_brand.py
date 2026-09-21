# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Brand-attribution model exposing the integrity-checked brand line
to QWeb templates and to UI computes.

QWeb cannot import Python directly, but it can call instance methods
on a singleton AbstractModel. This abstract model exposes
``brand_line()`` which delegates to the integrity verifier; every
PDF report that t-calls the report shell renders the brand line
through this model so the verifier fires once per report render.
"""
from odoo import api, models

from ..branding import integrity


class EhLogBrand(models.AbstractModel):
    _name = "eh.log.brand"
    _description = "ERP Heritage Brand Attribution"

    @api.model
    def brand_line(self):
        """Return the integrity-verified brand attribution string.

        Raises BrandIntegrityError when the chunks are tampered.
        Called by the report-shell footer template; the report
        rendering aborts if the verifier fails.
        """
        return integrity.brand_line()

    @api.model
    def brand_html(self):
        """Return the brand line wrapped for inline HTML rendering."""
        line = self.brand_line()
        return f'<span class="eh_brand_line">{line}</span>'
