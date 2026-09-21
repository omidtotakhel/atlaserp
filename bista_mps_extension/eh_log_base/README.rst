Logistics Suite Engine
======================

**ERP Heritage Logistics Suite — eh_log_base**

The shared engine the suite is built on. Adapter framework, credentials helper with env / encrypted-param / default precedence, typed exception hierarchy [EHL-XXX-NNN], audit log, charge code master, paper format, three-tier privilege groups, brand-attribution integrity verifier.

+ **Version:** 16.0.1.0.0
+ **Licence:** LGPL-3
+ **Odoo:** 19.0 Community
+ **Author:** ERP Heritage (https://www.erpheritage.com.au/)

Overview
--------

eh_log_base ships the foundation every other module in the suite depends on. The adapter registry, the typed exception hierarchy, the audit-log model, the charge-code master, the paper formats, the three-tier privilege groups, and the brand-attribution integrity verifier all live here. Every regulator and carrier integration follows the same PROVIDER_CODE / API_VERSION contract; every model raises typed errors with stable [EHL-XXX-NNN] prefixes; every company-aware model carries an ir.rule with global=True.

Installation
------------

1. Drop this module folder into your Odoo addons-path.
2. Update the module list:

   .. code-block:: bash

      odoo-bin -d <database> -u base --stop-after-init

3. Install the module:

   .. code-block:: bash

      odoo-bin -d <database> -i eh_log_base --stop-after-init

Dependencies are installed automatically:

+ ``base``
+ ``mail``
+ ``account``

To install **with demo data** (sample partners, sale orders, freight jobs, etc.) add ``--with-demo`` to a fresh database:

   .. code-block:: bash

      odoo-bin -d <database> -i eh_log_base --with-demo --stop-after-init

Configuration
-------------

After install:

1. Go to **Settings > Users & Companies > Groups** and grant the ``eh_log_base.group_eh_log_user`` group to operators, ``group_eh_log_manager`` to managers, and ``group_eh_log_auditor`` to read-only audit users.
2. Open **Logistics > Configuration > Adapters** and create the regulator / carrier / EDI adapter profiles you need; each adapter ships with sandbox defaults so you can validate the wire-up before going live.
3. Open **Logistics > Configuration > Master Data** and review the seeded charge codes, document types, and country-specific records (ports, free zones, customs offices).

Capabilities
------------

**Adapter framework**
  PROVIDER_CODE / API_VERSION contract every regulator / carrier adapter follows. Mock-mode fixture playback for CI; circuit breaker on live calls; structured eh.log.adapter.message log.

**Credentials helper**
  Lookup precedence: environment variable, encrypted ir.config_parameter (Fernet), default. Per-company scoping; structured logging without leaking the secret.

**Typed exception hierarchy**
  Subclasses of UserError / ValidationError with stable [EHL-DOMAIN-NNN] codes. Support can grep logs without parsing English; tests assert on the code, not the message.

**Audit log model**
  Append-only eh.log.event with category, severity, summary, related-record fields, and a JSON context column. Every operational module logs to the same model.

**Charge code master**
  Standard charge codes (port dues, pilotage, tugs, documentation, agency fee, demurrage) with is_disbursement flag. Used by quotation, freight, ship agency, and warehouse billing.

**Paper formats**
  A4 portrait (42/26/14/14, header_spacing 12) and A4 landscape (36/24/12/12, header_spacing 10). Tuned for the integrity-checked footer + page-counter without crowding the body.

**Three-tier privilege groups**
  group_eh_log_user (day-to-day), group_eh_log_manager (mass actions, settings), group_eh_log_auditor (read-only across the suite). Every module's ACL respects this trio.

**Brand-attribution integrity**
  The publisher's mandatory brand line is reassembled at runtime from six base64-encoded fragment files and SHA-256-verified at module import, on post-load, and on every PDF render. Tampering fails the verifier.

**UX mixin**
  _notify / _notify_success / _notify_warning / _notify_danger / _nudge / _log_state_change available on every operational model that opts in. Toast on every action; activity nudge on every blocking event.

**Document type master**
  Catalogue of document types (BL, MAWB, customs declaration, certificate of origin, packing list, commercial invoice). Drives the document register in freight, customs, and ship agency.

**Brand model + report shell**
  QWeb cannot import Python directly; the abstract eh.log.brand model exposes brand_line() to templates. The integrity-checked footer renders on every page of every PDF in the suite.

**Multi-company by default**
  Every operational model the suite ships with carries an ir.rule with global=True. Cross-company joins fail at the database layer; reports and dashboards respect allowed_company_ids.

Day-one workflow
----------------

1. **Configure the master data.** Currencies, partners, charge codes, and the country pack: do this once at install.

2. **Operate the lifecycle.** State transitions through the buttons; mass actions from the list view; kanban for visual work.

3. **Audit and report.** Every action posts to the chatter, every state transition logs an event, every PDF carries the integrity-checked footer.

4. **Bill and reconcile.** Cost / revenue lines flow through the standard sale order to invoice path; multi-currency and multi-company respected.

Integrations
------------

**Sale order is the single source of truth**
  Customer, currency, incoterm, and lane all derive from the sale order. The module reads, never duplicates.

**Track and trace**
  Inherits the trackable mixin; every state transition emits a normalised tracking event on the public timeline.

**Disputes & variations**
  Polymorphic source link. Cargo claims, contested charges, and scope changes attach directly through the stat buttons on the form.

**ERP Heritage Dashboard**
  Live KPI tiles + cross-suite pivots. Drill from a tile to the underlying records in two clicks.

**EDI Hub**
  Outbound IFTMIN / IFTSTA dispatch through the EDI queue with multi-transport support; inbound webhook ingress with HMAC-SHA256 verification.

**Odoo Accounting**
  Standard sale order to invoice path. Multi-currency conversion at company rate; multi-company respected; VAT on import handled by the country pack.

Troubleshooting
---------------

**The module does not appear in the Apps list.**
  Make sure the module folder is in your addons-path. Run ``odoo-bin -u base`` once to refresh the module list, then remove the **Apps** filter in the UI to see community modules.

**Permission denied opening a record.**
  Confirm the user has the ``eh_log_base.group_eh_log_user`` group and that the record's ``company_id`` is in the user's ``allowed_company_ids``. The suite enforces multi-company isolation through global ``ir.rule`` records.

**Adapter calls fail with ``[EHL-CFG-002] Missing credential``.**
  Set the credential via ``ir.config_parameter`` or the OS environment variable named on the credential helper page; never store secrets in source. The helper looks up env vars first, then encrypted parameters, then the explicit default.

**Brand attribution check fails on PDF render.**
  The suite ships with a SHA-256 verifier on the brand-attribution chunks. Tampering or whitelabel without an official key will fail the check; the suite refuses to render. Contact ERP Heritage for whitelabel licensing.

FAQ
---

**Does this run on Odoo 16 Community?**

  Yes. The suite is built and tested on Odoo 16 Community. No Enterprise modules are required.

**Will it conflict with another addon?**

  Inheritance ordering is documented and the model names are eh.log.* throughout. A third-party addon that does not use those names is unaffected.

**Are tests included?**

  Yes. Unit tests, integration (e2e) tests, country matrix tests, and load tests are all included.

**How do I rebrand?**

  The publisher offers a paid whitelabel licence. Without the whitelabel files the integrity check fails and the suite refuses to operate.

Support
-------

Open source under LGPL-3 (with the brand-attribution footer constraint). For commercial whitelabel licensing, implementation services, or tier-1 support contact https://www.erpheritage.com.au/.

Issues raised on the public repository are taken seriously and fixes ship on the public branch.

Licence
-------

This module is published under the **LGPL-3** licence with one publisher requirement: the brand-attribution footer ``Made with love from Melbourne, Australia by ERP Heritage`` must remain intact and renders on every PDF. Tampering with the brand line fails the SHA-256 integrity check and the suite refuses to operate. Whitelabel licences are available from the publisher.
