# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Adapter profile model.

One row per (provider, company) configuration. Stores endpoint URLs,
environment selector, version implemented, credential references, rate
limit configuration, feature flags, and last health check status.

Endpoints are master data, not constants in code. Country localisation
modules ship default profile records pointing at the published sandbox
endpoints; operators flip the environment selector and supply
credentials to switch to production.
"""
import logging

from odoo import _, api, fields, models

from ..exceptions import AdapterAuthError, ConfigurationMissingError

_logger = logging.getLogger(__name__)


class EhLogAdapterProfile(models.Model):
    _name = "eh.log.adapter.profile"
    _description = "Logistics Adapter Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "provider_code, company_id, environment"
    _rec_names_search = ["display_name", "provider_code", "name"]

    # ----- Identity -----

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="Operator-friendly label for this profile, e.g. 'Mirsal 2 (UAE Sandbox)'.",
    )

    provider_code = fields.Char(
        string="Provider Code",
        required=True,
        index=True,
        tracking=True,
        help="Stable provider identifier referenced by adapter classes "
             "(e.g. 'mirsal2', 'fasah', 'dcsa', 'iata_cargo_xml'). "
             "Adapter dispatch keys on this code; do not rename in place.",
    )

    provider_kind = fields.Selection(
        selection=[
            ("regulator", "Government Regulator"),
            ("carrier_ocean", "Ocean Carrier"),
            ("carrier_air", "Air Carrier"),
            ("carrier_express", "Express Carrier"),
            ("carrier_rail", "Rail Carrier"),
            ("edi_partner", "EDI Partner"),
            ("telematics", "Telematics Provider"),
            ("routing", "Routing or Mapping"),
            ("screening", "Sanctions or PEP Screening"),
            ("payment", "Payment Provider"),
            ("other", "Other"),
        ],
        string="Provider Kind",
        required=True,
        tracking=True,
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    company_ids = fields.Many2many(
        "res.company",
        "eh_log_adapter_profile_company_rel",
        "profile_id",
        "company_id",
        string="Companies",
        compute="_compute_company_ids",
        store=True,
        index=True,
        precompute=True,
        help="Mirrors company_id as an m2m so the global isolation rule "
             "can use a single 'company_ids in company_ids' domain that "
             "holds whether the field is mono or multi-company in the "
             "future.",
    )

    # ----- Environment -----

    environment = fields.Selection(
        selection=[
            ("mock", "Mock (offline fixtures)"),
            ("sandbox", "Sandbox"),
            ("production", "Production"),
        ],
        string="Environment",
        required=True,
        default="mock",
        tracking=True,
        help="Mock plays back canned fixtures from tests/fixtures/. "
             "Sandbox calls the provider's published test environment. "
             "Production hits live. Profiles default to mock so a "
             "fresh install never accidentally calls a real regulator.",
    )

    endpoint_url = fields.Char(
        string="Primary Endpoint",
        tracking=True,
        help="Base URL for sandbox or production calls. Mock environment "
             "ignores this field. Reference data files supply the "
             "published default; operators override for private endpoints.",
    )

    secondary_endpoint_url = fields.Char(
        string="Secondary Endpoint",
        help="Optional fallback URL used by adapters that publish a "
             "DR or read-replica endpoint.",
    )

    api_version = fields.Char(
        string="API Version Implemented",
        required=True,
        tracking=True,
        help="Provider API version this profile speaks (e.g. '2.4', "
             "'2026-01'). Adapters refuse to dispatch when this does "
             "not match the implementing class's declared version.",
    )

    # ----- Authentication -----

    auth_method = fields.Selection(
        selection=[
            ("api_key", "API Key"),
            ("oauth2_client_credentials", "OAuth2 Client Credentials"),
            ("oauth2_authorization_code", "OAuth2 Authorization Code"),
            ("mtls", "Mutual TLS"),
            ("jwt_signed", "JWT Signed (private key)"),
            ("as2", "AS2 (EDI)"),
            ("sftp_key", "SFTP Key"),
            ("basic", "HTTP Basic"),
            ("none", "None"),
        ],
        string="Authentication Method",
        required=True,
        default="api_key",
        tracking=True,
    )

    credential_purpose = fields.Char(
        string="Credential Purpose Key",
        required=True,
        help="Logical key passed to eh.log.credentials.get(). The helper "
             "resolves it via environment variables and ir.config_parameter "
             "without exposing the secret on this form.",
    )

    credential_status = fields.Selection(
        selection=[
            ("unknown", "Unknown"),
            ("ok", "Resolved"),
            ("missing", "Missing"),
        ],
        string="Credential Status",
        compute="_compute_credential_status",
        store=False,
        help="Live status of the credential as resolved by the helper. "
             "Read-only; recompute by clicking Test Credential.",
    )

    # ----- Resilience -----

    request_timeout_seconds = fields.Integer(
        string="Request Timeout (s)",
        default=30,
        required=True,
        help="Per-call timeout. Adapter raises AdapterTimeoutError on "
             "expiry and the circuit breaker increments its counter.",
    )

    retry_max_attempts = fields.Integer(
        string="Retry Max Attempts",
        default=3,
        required=True,
        help="Maximum retry attempts on transient errors. Backoff is "
             "exponential with jitter, base 1.5x.",
    )

    circuit_breaker_threshold = fields.Integer(
        string="Circuit Breaker Threshold",
        default=5,
        required=True,
        help="Consecutive failure count that trips the circuit breaker. "
             "While tripped, the adapter rejects calls immediately and "
             "schedules a half-open probe.",
    )

    circuit_breaker_cooldown_seconds = fields.Integer(
        string="Circuit Breaker Cooldown (s)",
        default=60,
        required=True,
        help="Time to wait before the half-open probe runs.",
    )

    rate_limit_per_minute = fields.Integer(
        string="Rate Limit (per minute)",
        default=0,
        help="Soft per-minute rate limit honoured client-side. 0 means "
             "no client-side throttling; the adapter still respects "
             "server-side 429 responses.",
    )

    # ----- Health -----

    health_check_status = fields.Selection(
        selection=[
            ("unknown", "Not Yet Checked"),
            ("ok", "Healthy"),
            ("degraded", "Degraded"),
            ("down", "Down"),
        ],
        string="Health Status",
        default="unknown",
        readonly=True,
        tracking=True,
        index=True,
    )

    health_check_at = fields.Datetime(
        string="Health Checked At",
        readonly=True,
    )

    health_check_message = fields.Text(
        string="Health Check Message",
        readonly=True,
    )

    health_check_latency_ms = fields.Integer(
        string="Last Health Latency (ms)",
        readonly=True,
    )

    # ----- Counters -----

    message_count = fields.Integer(
        string="Messages",
        compute="_compute_message_count",
        help="Total messages logged against this profile.",
    )

    last_message_at = fields.Datetime(
        string="Last Message",
        compute="_compute_message_count",
    )

    # ----- Display -----

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    active = fields.Boolean(default=True, tracking=True)

    notes = fields.Html(string="Operational Notes")

    # ----- SQL constraints -----

    _sql_constraints = [
        (
            'provider_company_environment_unique',
            'UNIQUE(provider_code, company_id, environment)',
            'Only one profile per (provider, company, environment) is allowed. If you need a second sandbox configuration, use the secondary endpoint field on the existing profile.',
        ),
    ]

    # ----- Computes -----

    @api.depends("company_id")
    def _compute_company_ids(self):
        for profile in self:
            profile.company_ids = profile.company_id

    @api.depends("name", "provider_code", "environment")
    def _compute_display_name(self):
        for profile in self:
            env_label = dict(self._fields["environment"].selection).get(
                profile.environment, profile.environment,
            )
            profile.display_name = (
                f"{profile.name or profile.provider_code} ({env_label})"
            )

    @api.depends_context("uid")
    def _compute_credential_status(self):
        Credentials = self.env["eh.log.credentials"]
        for profile in self:
            if not profile.credential_purpose:
                profile.credential_status = "unknown"
                continue
            try:
                Credentials.get(
                    profile.credential_purpose,
                    env_vars=profile._suggested_env_vars(),
                    param_key=profile._param_key(),
                    company_id=profile.company_id.id,
                )
                profile.credential_status = "ok"
            except Exception:
                # Helper raises CredentialsMissingError; widen the catch
                # so a transient issue (e.g. crypto library missing) does
                # not prevent the form from rendering.
                profile.credential_status = "missing"

    def _compute_message_count(self):
        Message = self.env["eh.log.adapter.message"]
        for profile in self:
            messages = Message.search(
                [("profile_id", "=", profile.id)],
                order="created_at desc",
                limit=1,
            )
            profile.message_count = Message.search_count(
                [("profile_id", "=", profile.id)]
            )
            profile.last_message_at = messages.created_at if messages else False

    # ----- Public actions -----

    def action_run_health_check(self):
        """Manual health check trigger.

        Concrete adapter classes register themselves under
        provider_code; this action looks up the registered class and
        invokes its ``health_check`` method. If no adapter is
        registered for the provider, a clean ConfigurationMissingError
        surfaces with the list of registered providers.
        """
        from .. import adapter_registry  # local import: avoids cycle
        for profile in self:
            adapter_cls = adapter_registry.get(profile.provider_code)
            if not adapter_cls:
                raise ConfigurationMissingError(
                    5,
                    _(
                        "No adapter class is registered for provider "
                        "code '%(code)s'. Available providers: %(list)s. "
                        "If this is a new integration, the country pack "
                        "or vertical module that owns it has not been "
                        "installed."
                    ) % {
                        "code": profile.provider_code,
                        "list": ", ".join(sorted(adapter_registry.keys())) or "(none)",
                    },
                )
            adapter = adapter_cls(profile)
            adapter.health_check()
        return True

    def action_test_credential(self):
        """Force a credential resolution attempt and refresh status."""
        Credentials = self.env["eh.log.credentials"]
        for profile in self:
            try:
                Credentials.get(
                    profile.credential_purpose,
                    env_vars=profile._suggested_env_vars(),
                    param_key=profile._param_key(),
                    company_id=profile.company_id.id,
                )
            except Exception as exc:
                raise AdapterAuthError(
                    6,
                    _(
                        "Credential for profile %(name)s is not "
                        "resolvable. Underlying error: %(err)s"
                    ) % {"name": profile.display_name, "err": str(exc)},
                ) from exc
        return True

    def action_view_messages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Adapter Messages"),
            "res_model": "eh.log.adapter.message",
            "view_mode": "list,form",
            "domain": [("profile_id", "=", self.id)],
            "context": {"default_profile_id": self.id},
        }

    # ----- Internals -----

    def _suggested_env_vars(self) -> list:
        """Convention for environment-variable lookup names.

        Each profile derives candidate env var names from the provider
        code and credential purpose so the operator can grep their
        deployment configuration without consulting documentation.
        """
        self.ensure_one()
        provider = (self.provider_code or "").upper()
        purpose = (self.credential_purpose or "").upper().replace(".", "_")
        return [
            f"EH_LOG_{provider}_{purpose}",
            f"EH_LOG_{provider}",
        ]

    def _param_key(self) -> str:
        """ir.config_parameter key suffix passed to the credentials helper."""
        self.ensure_one()
        return f"{(self.provider_code or '').lower()}.{self.credential_purpose or ''}"
