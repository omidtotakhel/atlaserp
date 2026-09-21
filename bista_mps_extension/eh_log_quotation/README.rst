Logistics Quotation
===================

**ERP Heritage Logistics Suite — eh_log_quotation**

Sale order extension built for freight: live margin guard, live credit guard, live KYC guard, charge templates by lane and mode, manager approval flow when a guard pings, preflight checklist before confirmation.

+ **Version:** 16.0.1.0.0
+ **Licence:** LGPL-3
+ **Odoo:** 19.0 Community
+ **Author:** ERP Heritage (https://www.erpheritage.com.au/)

Overview
--------

eh_log_quotation extends sale.order with the three guards every freight quote needs: margin (warning + floor), credit exposure (live partner receivables vs limit), and KYC (documents on file vs expiry window). Mode + direction + lane + incoterm carry on the same record. Charge templates pre-fill line items by lane; the preflight wizard runs before confirmation; manager approval is gated and audited.

Installation
------------

1. Drop this module folder into your Odoo addons-path.
2. Update the module list:

   .. code-block:: bash

      odoo-bin -d <database> -u base --stop-after-init

3. Install the module:

   .. code-block:: bash

      odoo-bin -d <database> -i eh_log_quotation --stop-after-init

Dependencies are installed automatically:

+ ``eh_log_base``
+ ``sale_management``
+ ``account``

To install **with demo data** (sample partners, sale orders, freight jobs, etc.) add ``--with-demo`` to a fresh database:

   .. code-block:: bash

      odoo-bin -d <database> -i eh_log_quotation --with-demo --stop-after-init

Configuration
-------------

After install:

1. Go to **Settings > Users & Companies > Groups** and grant the ``eh_log_base.group_eh_log_user`` group to operators, ``group_eh_log_manager`` to managers, and ``group_eh_log_auditor`` to read-only audit users.
2. Open **Logistics > Configuration > Adapters** and create the regulator / carrier / EDI adapter profiles you need; each adapter ships with sandbox defaults so you can validate the wire-up before going live.
3. Open **Logistics > Configuration > Master Data** and review the seeded charge codes, document types, and country-specific records (ports, free zones, customs offices).

Capabilities
------------

**Margin guard live**
  Healthy / Warning / Below Floor with company-configured thresholds; disbursements excluded; margin %% recomputes on every line edit.

**Credit exposure live**
  Outstanding receivables in company currency vs the partner's approved limit; OK / Warning / Blocked. Block confirmation if hard exceeded.

**KYC guard live**
  OK / Warning / Expired / Not Assessed. The warning window is per company; expired documents block confirmation; manager override audited.

**Charge template by lane / mode**
  Apply-template wizard fills line items based on lane + mode + direction. Disbursements flagged; rate sheets resolved; the operator can override per line.

**Preflight checklist**
  One-click validation: margin / credit / KYC / lane / incoterm / documents present. Wizard surfaces every soft warning so the operator decides before customer-visible confirmation.

**Manager approval gated**
  When any guard pings, confirmation is gated until a manager approves. Approval logs the user, timestamp, reasons, and writes an eh.log.event entry.

**Mass actions**
  Mass-approve, mass-cancel with reason, mass-send-for-review with deadline. Manager-only or user-only as appropriate; toast confirms the count.

**Smart-form onchanges**
  Pick a partner: credit / KYC posture surfaces. Pick a mode: logistics flag auto-sets. Pick a direction: country pair auto-defaults from the company address.

**Volumetric weight check**
  1 cbm = 1000 kg conversion fires when volumetric dominates by 1.5x or more; the operator gets a soft warning before the customer sees the rate.

**Charge code disbursement flag**
  Charge codes carry is_disbursement; disbursement lines bypass the margin computation so the agency-fee structure stays honest.

**Activity nudges**
  Quotations awaiting approval surface as activity rows on the responsible user's inbox; SLA breach lights the row red.

**Comprehensive search**
  Filters: state, mode, direction, margin status, credit status, KYC status, period (today/week/month/year). Group-by: state, mode, customer, lane.

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
