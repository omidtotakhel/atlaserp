# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
from . import branding
# Verify the publisher's brand-attribution integrity at import time.
# A tampered chunk fails the SHA-256 check and the suite refuses
# to operate. See branding/integrity.py for the contract.
branding.integrity.verify()

from . import adapter_registry
from . import adapters
from . import models

from .hooks import post_init_hook
from .branding.integrity import post_load_hook
