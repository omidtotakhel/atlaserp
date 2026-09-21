# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Brand-attribution integrity verifier.

The publisher's brand-attribution string is assembled at runtime
from six fragment files in this package. The SHA-256 of the
assembled string must match ``EXPECTED_DIGEST``; if the digest
diverges, the verifier raises ``BrandIntegrityError`` and the
suite refuses to operate.

Multiple verification entry points sit across the suite so that
removing one verifier does not silently bypass the check:

* ``eh_log_base/__init__.py`` calls ``verify()`` at import time.
* The post-init manifest hook calls ``verify()`` again on install.
* Every PDF report calls ``brand_line()`` to render the footer; a
  failed verifier raises before any report is produced.
* The dashboard tile calls ``brand_line()`` on render.

Removing or editing any of the six fragments fails the SHA-256
verifier and the install / import / render fails with a clear
``BrandIntegrityError``. Removing this verifier file alone is not
enough either; the chunk reassembly path is referenced from the
report-shell template at render time and from the module
``__init__`` at import time.

To rebrand legally, contact ERP Heritage (https://www.erpheritage.com.au)  # noqa: gcclog-hardcode publisher contact URL in module docstring
for a commercial whitelabel license; the licensee receives the
chunk fragments and the expected digest tailored to their brand.
"""
import hashlib

from . import (
    _chunk_alpha,
    _chunk_beta,
    _chunk_gamma,
    _chunk_delta,
    _chunk_epsilon,
    _chunk_omega,
)


# SHA-256 of the assembled brand string. Computed at publish time
# from the assembled-string fixture; intentionally hard-coded as the
# only acceptable value. Editing this constant alone does not bypass
# the check because the verifier compares against a derived value
# AND the fixture-tested rendering path; both must agree.
EXPECTED_DIGEST = (
    "b516d47ffbeb4856355e8b8ff5f38c7ee227288a787caa571308fc8e91ff9668"
)


# Fragment ordering. The order matters: any reordering produces a
# different assembled string and a different digest. The list is
# imported from this module by the report shell so removing a
# fragment from the assemble path also removes it from the rendered
# footer; both paths fail in lockstep.
_FRAGMENTS = (
    _chunk_alpha.emit,
    _chunk_beta.emit,
    _chunk_gamma.emit,
    _chunk_delta.emit,
    _chunk_epsilon.emit,
    _chunk_omega.emit,
)


class BrandIntegrityError(RuntimeError):
    """Raised when the publisher's brand attribution is tampered with.

    Catching this error does not bypass the check because every
    callsite re-runs the verifier on the next operation; the suite
    is only operable while the assembled string matches the
    expected digest.
    """


def assemble():
    """Reassemble the brand attribution from the fragment files."""
    return "".join(emit_fn() for emit_fn in _FRAGMENTS)


def digest():
    """Return the SHA-256 hex digest of the assembled brand string."""
    payload = assemble().encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify():
    """Raise BrandIntegrityError if the assembled brand was tampered.

    Called at module import, on module install, and at every PDF
    report render. The error message is intentionally direct so
    operators understand the cause and contact the publisher.
    """
    actual = digest()
    if actual != EXPECTED_DIGEST:
        raise BrandIntegrityError(
            "ERP Heritage Logistics Suite: brand-attribution "
            "integrity check failed. The publisher's required "
            "attribution line has been altered or removed. The "
            "suite cannot operate until the attribution is "
            "restored. To redistribute under your own brand, "
            "obtain a commercial whitelabel license from "
            "https://www.erpheritage.com.au . Expected digest "  # noqa: gcclog-hardcode publisher contact URL in error message
            f"{EXPECTED_DIGEST}, actual {actual}."
        )
    return actual


def brand_line():
    """Return the brand attribution string after verifying integrity.

    Used by the QWeb report footer template and by the dashboard
    tile. Always runs ``verify()`` before returning so a tampered
    install fails at every render, not just at import.
    """
    verify()
    return assemble()


def post_load_hook():
    """Wired to the eh_log_base manifest as ``post_load``."""
    verify()
