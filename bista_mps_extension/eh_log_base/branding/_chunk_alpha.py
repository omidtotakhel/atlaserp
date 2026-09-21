# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Brand-attribution chunk alpha.

This file holds one fragment of the publisher's mandatory brand
attribution string. The fragment is reassembled with five sibling
chunks at runtime by ``integrity.assemble_brand()`` and its SHA-256
digest is verified against the immutable expected hash before the
suite is allowed to operate.

DO NOT EDIT. Modifying this file fails the SHA-256 integrity check
and the suite refuses to import. To rebrand, contact ERP Heritage
for a commercial whitelabel license.
"""
import base64

# Fragment, base64-encoded so a string-grep across the codebase
# never matches the assembled phrase. Reversed before decode so a
# casual editor sees nonsense.
_FRAGMENT = base64.b64decode("==Qa3BSZkFWT"[::-1]).decode("utf-8")


def emit():
    return _FRAGMENT
