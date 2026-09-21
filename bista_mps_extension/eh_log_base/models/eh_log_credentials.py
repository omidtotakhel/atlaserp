# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Credentials helper for the ERP Heritage logistics suite.

Resolves secrets from a documented precedence chain:

1. Environment variable (one or more candidate names tried in order).
2. ir.config_parameter slot, optionally encrypted at rest.
3. Explicit default supplied by the caller (use sparingly; defaults
   should be None so missing credentials surface immediately).

The helper never logs the resolved value. It logs the lookup attempt
(env var name, parameter key) and the outcome (resolved or missing) so
operators can debug configuration without leaking secrets.

Encryption at rest uses Fernet (cryptography library) with a key
derived from the database UUID and the system parameter
`eh_log.credentials.encryption_salt`. The salt is created on first
use; rotating it requires re-encrypting every stored secret. The salt
is namespace-scoped to the logistics suite; the accounting suite is
unaffected.

The cryptography dependency is optional. If `cryptography` is not
installed, encryption is unavailable and the helper raises
ConfigurationMissingError on any encrypted-write attempt while still
allowing plaintext-parameter and env-var lookups. This keeps the
suite installable on a stripped-down deployment that does not need
encrypted-at-rest secrets.
"""
import base64
import hashlib
import logging
import os
from typing import Iterable, Optional

from odoo import _, api, models

from ..exceptions import (
    ConfigurationMissingError,
    CredentialsMissingError,
)

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except ImportError:
    Fernet = None
    InvalidToken = Exception
    _CRYPTO_AVAILABLE = False


CONFIG_SALT_PARAM = "eh_log.credentials.encryption_salt"
CONFIG_PREFIX = "eh_log.credentials."
ENCRYPTED_VALUE_PREFIX = "enc::v1::"


class EhLogCredentials(models.AbstractModel):
    """Resolve secrets for adapters without ever hard-coding them.

    Usage from an adapter:

        api_key = self.env['eh.log.credentials'].get(
            'mirsal_api_key',
            env_vars=['EH_LOG_MIRSAL_API_KEY', 'MIRSAL_API_KEY'],
            param_key='mirsal.api_key',
        )

    Returns the resolved string. Raises CredentialsMissingError if
    nothing yields a value and no default is provided.
    """

    _name = "eh.log.credentials"
    _description = "Logistics Credentials Helper"

    # ----- Lookup -----

    @api.model
    def get(
        self,
        purpose: str,
        env_vars: Optional[Iterable[str]] = None,
        param_key: Optional[str] = None,
        default: Optional[str] = None,
        company_id: Optional[int] = None,
    ) -> str:
        """Resolve a credential against the documented precedence chain.

        :param purpose: short label used in error messages and logs
            (e.g. 'mirsal_api_key'). Never the secret value itself.
        :param env_vars: iterable of environment variable names tried
            in order. The first non-empty value wins.
        :param param_key: ir.config_parameter key suffix; the helper
            prepends ``eh_log.credentials.``. Per-company keys are
            supported by passing ``company_id``; the lookup tries
            ``<key>.company.<id>`` first, then ``<key>``.
        :param default: explicit fallback. Use sparingly.
        :param company_id: scope per-company lookups.
        :returns: the resolved string.
        :raises CredentialsMissingError: when nothing yields a value
            and no default is provided.
        """
        env_vars = list(env_vars or [])

        # 1. Environment variables, in declared order.
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                _logger.debug(
                    "eh.log.credentials: %s resolved from env %s",
                    purpose, var,
                )
                return value

        # 2. ir.config_parameter, with optional company scoping.
        if param_key:
            full_key = f"{CONFIG_PREFIX}{param_key}"
            tried_keys = []
            if company_id:
                scoped = f"{full_key}.company.{company_id}"
                tried_keys.append(scoped)
            tried_keys.append(full_key)
            ICP = self.env['ir.config_parameter'].sudo()
            for key in tried_keys:
                value = ICP.get_param(key)
                if value:
                    decoded = self._decode_if_encrypted(value)
                    _logger.debug(
                        "eh.log.credentials: %s resolved from param %s",
                        purpose, key,
                    )
                    return decoded

        # 3. Explicit default.
        if default is not None:
            _logger.debug(
                "eh.log.credentials: %s resolved from caller default",
                purpose,
            )
            return default

        # No source yielded a value: fail loud with actionable hint.
        env_hint = ", ".join(env_vars) if env_vars else _("(none configured)")
        param_hint = (
            f"{CONFIG_PREFIX}{param_key}" if param_key
            else _("(none configured)")
        )
        raise CredentialsMissingError(
            1,
            _(
                "Credential for '%(purpose)s' is not configured. "
                "Tried environment variables: %(env)s. Tried "
                "ir.config_parameter key: %(param)s. Set one of these "
                "values in your deployment configuration or under "
                "Settings > ERP Heritage Logistics > Adapters."
            ) % {
                "purpose": purpose,
                "env": env_hint,
                "param": param_hint,
            },
        )

    # ----- Encrypt / decrypt at rest -----

    @api.model
    def set_encrypted(self, param_key: str, value: str) -> None:
        """Store a secret in ir.config_parameter, encrypted at rest.

        Refuses if the cryptography library is not installed; the
        operator can still store secrets in plaintext via the standard
        Settings UI in that case (and the helper will read them back),
        but the encrypted path is unavailable.
        """
        if not _CRYPTO_AVAILABLE:
            raise ConfigurationMissingError(
                2,
                _(
                    "Encrypted credential storage requires the Python "
                    "'cryptography' library. Install it on the server "
                    "or store credentials via environment variables "
                    "instead."
                ),
            )
        token = Fernet(self._derive_key()).encrypt(value.encode("utf-8"))
        full_key = f"{CONFIG_PREFIX}{param_key}"
        encoded = ENCRYPTED_VALUE_PREFIX + token.decode("utf-8")
        self.env['ir.config_parameter'].sudo().set_param(full_key, encoded)

    @api.model
    def _decode_if_encrypted(self, raw: str) -> str:
        """Return the plaintext value for an ir.config_parameter row.

        Detects the encrypted prefix and decodes via Fernet; otherwise
        returns the raw value unchanged so plaintext entries set via
        the UI still work.
        """
        if not raw or not raw.startswith(ENCRYPTED_VALUE_PREFIX):
            return raw
        if not _CRYPTO_AVAILABLE:
            raise ConfigurationMissingError(
                3,
                _(
                    "An encrypted credential is stored but the Python "
                    "'cryptography' library is not installed on the "
                    "server. Install it or replace the parameter with "
                    "an environment variable."
                ),
            )
        token = raw[len(ENCRYPTED_VALUE_PREFIX):].encode("utf-8")
        try:
            plain = Fernet(self._derive_key()).decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise ConfigurationMissingError(
                4,
                _(
                    "An encrypted credential could not be decrypted. "
                    "The encryption salt or database UUID has changed. "
                    "Re-set the credential under Settings > ERP "
                    "Heritage Logistics > Adapters."
                ),
            ) from exc
        return plain

    @api.model
    def _derive_key(self) -> bytes:
        """Derive a Fernet key from the DB UUID plus a per-suite salt.

        The salt is auto-created on first use if absent. The DB UUID
        comes from the standard ``database.uuid`` ir.config_parameter
        Odoo seeds at install. Together they bind encrypted secrets to
        the originating database; a copied database without the salt
        cannot decrypt secrets, which is the desired property.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        db_uuid = ICP.get_param("database.uuid", default="")
        salt = ICP.get_param(CONFIG_SALT_PARAM)
        if not salt:
            salt = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")
            ICP.set_param(CONFIG_SALT_PARAM, salt)
        material = f"{db_uuid}|{salt}".encode("utf-8")
        digest = hashlib.sha256(material).digest()
        return base64.urlsafe_b64encode(digest)
