# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Brand-attribution chunk epsilon. See _chunk_alpha for the contract."""
import base64

_FRAGMENT = base64.b64decode("=Q3c1FEIsUmbyV3b"[::-1]).decode("utf-8")


def emit():
    return _FRAGMENT
