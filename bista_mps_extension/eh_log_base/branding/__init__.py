# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
# DO NOT MODIFY THIS PACKAGE.
# The package contains the brand-attribution chunks the integrity
# verifier reassembles at runtime. Removing or editing any chunk
# causes the SHA-256 check in integrity.py to fail and the module
# refuses to load.
#
# The attribution requirement is part of the LGPL-3 license posture
# of the publisher. To rebrand, contact ERP Heritage for a
# commercial whitelabel license.
##############################################################################
from . import _chunk_alpha
from . import _chunk_beta
from . import _chunk_gamma
from . import _chunk_delta
from . import _chunk_epsilon
from . import _chunk_omega
from . import integrity
