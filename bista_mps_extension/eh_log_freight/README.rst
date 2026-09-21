Freight Forwarding
==================

**ERP Heritage Logistics Suite — eh_log_freight**

The forwarding job spine for the GCC. State-machine guarded lifecycle from booking to closed file, milestone log, ISO 6346 container register, BL/HBL/MBL/HAWB/MAWB issuance, cost and revenue ledger that posts to the same sale order the quotation lives on.

+ **Version:** 16.0.1.0.0
+ **Licence:** LGPL-3
+ **Odoo:** 19.0 Community
+ **Author:** ERP Heritage (https://www.erpheritage.com.au/)

Overview
--------

eh_log_freight is the spine of the suite. It hosts the freight forwarding job, the milestone log, the ISO 6346 container register, the bill-of-lading register (HBL/MBL for ocean, HAWB/MAWB for air), and the cost / revenue ledger that mirrors the matching sale order. The job state machine is gated end-to-end and emits tracking events on every transition; downstream modules (customs, transport, track-and-trace, EDI, carrier portal, disputes) compose with the job through stable foreign keys and the typed exception hierarchy.

Installation
------------

1. Drop this module folder into your Odoo addons-path.
2. Update the module list:

   .. code-block:: bash

      odoo-bin -d <database> -u base --stop-after-init

3. Install the module:

   .. code-block:: bash

      odoo-bin -d <database> -i eh_log_freight --stop-after-init

Dependencies are installed automatically:

+ ``eh_log_base``
+ ``eh_log_quotation``
+ ``sale_management``
+ ``account``
+ ``stock``

To install **with demo data** (sample partners, sale orders, freight jobs, etc.) add ``--with-demo`` to a fresh database:

   .. code-block:: bash

      odoo-bin -d <database> -i eh_log_freight --with-demo --stop-after-init

Configuration
-------------

After install:

1. Go to **Settings > Users & Companies > Groups** and grant the ``eh_log_base.group_eh_log_user`` group to operators, ``group_eh_log_manager`` to managers, and ``group_eh_log_auditor`` to read-only audit users.
2. Open **Logistics > Configuration > Adapters** and create the regulator / carrier / EDI adapter profiles you need; each adapter ships with sandbox defaults so you can validate the wire-up before going live.
3. Open **Logistics > Configuration > Master Data** and review the seeded charge codes, document types, and country-specific records (ports, free zones, customs offices).

Capabilities
------------

**Job state machine**
  draft → booked → in_transit → at_destination → delivered → closed (or cancelled). Direct writes blocked with [EHL-FRT-001]; transitions emit tracking events automatically.

**ISO 6346 container register**
  Container number with checksum validation, ISO type code, seal numbers, gross / tare / payload, owner-operator partner, and lifecycle dates (gate-in, loaded, sailed, discharged, gate-out).

**Multi-mode bills of lading**
  HBL / MBL for ocean, HAWB / MAWB for air. Carrier and shipper / consignee reference fields, plus the freight-prepaid / collect indicator. Renders to PDF via the integrity-checked report shell.

**Cost and revenue ledger**
  Posts on the same sale order the quote lives on. Disbursements excluded from margin computation; live margin status reflects accruals as the job advances and supplier bills land.

**Milestone log**
  Per-job timestamped event log: NOR tendered, vessel arrived, discharge complete, customs released, container gate-out, POD signed. Append-only; every state transition logs.

**Mode-aware UX**
  Sea / Air / Road / Rail / Multimodal. Mode selection drives the kanban grouping, the search filter chip set, and the BL form variant. Volumetric weight check fires at 1 cbm = 1000 kg.

**Lane-aware onchanges**
  Customer pick auto-defaults shipper / consignee per direction; party-country mismatch surfaces as a soft warning before customs declaration; same-country lane pings the operator unless cross-trade.

**Carrier-aware tracking**
  Inherits the trackable mixin. Every state transition emits a normalised tracking event; carrier IFTSTA inbound feeds map automatically. Public tracking page works without authentication.

**Customs hand-off**
  Spawns a customs declaration of the right type (import / export / transit) with the regulator of record from the destination country. The declaration carries every reference back.

**Mass-advance wizard**
  Operator picks N jobs from the list view and advances them all to the next state in one transaction. State machine still validates each; incompatible jobs are skipped and reported.

**Polymorphic disputes / variations**
  Cargo damage claim, contested charge, scope change, all attach polymorphically. Stat buttons on the form open the existing cases pre-filtered.

**Profitability dashboard**
  Dashboard tile + cross-suite pivot: revenue / cost / margin per customer, lane, mode, period. Drills down to the underlying jobs in two clicks.

Day-one workflow
----------------

1. **Apply quotation template.** Pick the lane and mode; the charge template pre-fills line items, defaults the incoterm, and seeds the carrier choice.

2. **Confirm the sale order.** Margin / credit / KYC guards run; if the trio is green the freight job spawns automatically with the matching origin / destination / mode.

3. **Book with the carrier.** Carrier portal rate-shop, IFTMIN dispatch, or manual booking against an external reference. The booking links back to the freight job.

4. **Operate through milestones.** Each state transition emits a milestone, a tracking event, and a chatter line. Mass-advance the kanban for batches; drill the pivot for lane analytics.

5. **Customs declare and clear.** Spawn the declaration of the right type. Adapter submits to the regulator of record and polls status until cleared or rejected.

6. **Deliver and collect POD.** Transport trip or last-mile delivery completes with a signed POD. Tracking event renders on the public page.

7. **Bill and reconcile.** Cost lines arrive from supplier bills; revenue lines invoice the customer; the margin status reconciles to the quote at job close.

8. **Close the file.** All milestones logged, all costs accrued, all POD images attached. Closed state is terminal; post-close changes flow through a variation.

Integrations
------------

**ERP Heritage Quotation**
  Sale order is the single source of truth. The freight job inherits the customer, currency, incoterm, and lane from the matching quotation; credit / KYC / margin guards run before confirmation.

**ERP Heritage Customs**
  Spawns a declaration of the right type with the regulator of record; the declaration carries the freight job reference and shares the cost / duty ledger.

**ERP Heritage Transport**
  Trip records on road / rail moves attach to the freight job through the standard reference; trip state transitions emit tracking events on the same timeline.

**ERP Heritage Track and Trace**
  Public tracking page renders the freight-job timeline at a non-enumerable token URL. Webhook ingress + IFTSTA inbound translator update the timeline automatically.

**ERP Heritage EDI Hub**
  IFTMIN forwarding instruction queues on freight dispatch; carriers post IFTSTA back. Multi-transport (SFTP / SMTP / HTTP / AS2) per partner.

**ERP Heritage Carrier Portal**
  Rate-shop across configured carriers in parallel; booking confirms back into the freight job; status polling cron updates the tracking timeline.

**ERP Heritage Disputes & Variations**
  Polymorphic source link. A damage claim, a contested charge, or a re-routing variation all attach directly to the freight job; stat buttons drill down.

**Odoo Accounting**
  Cost and revenue lines flow through the standard sale order to invoice path. Currency conversion uses the company rate at job close. Multi-company respected.

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

  Yes. The suite is built and tested on Odoo 16 Community. No Enterprise modules are required; Community + sale_management + account + stock is the minimum set.

**Will it conflict with another forwarding addon?**

  Possibly. The freight job model uses the eh.log.freight.job name; a third-party forwarder with a different model is unaffected. Where two modules share a model name (rare), inheritance ordering is documented.

**What's the licence?**

  LGPL-3 with one publisher requirement: the brand-attribution footer 'Made with ♥ from Melbourne, Australia by ERP Heritage' must remain intact and renders on every PDF. Tampering with the brand line fails the SHA-256 integrity check and the suite refuses to operate. Whitelabel licences are available from the publisher.

**Are tests included?**

  Yes. Unit tests, integration (e2e) tests, country matrix tests, and load tests are all included. Run with `odoo-bin --test-enable -i eh_log_freight` against a test database; the suite is also exercised by the documented test matrix.

**Can I extend the customs adapter?**

  Yes. Adapters follow the PROVIDER_CODE / API_VERSION contract. Subclass the country adapter in your own module to override the message map or wire a different transport; the base credentials helper and audit log keep working.

**How do I rebrand for my company?**

  The publisher offers a paid whitelabel licence that supplies you with replacement brand chunks and an updated SHA-256 expected digest. Without the whitelabel files the integrity check fails and the suite refuses to operate. Contact https://www.erpheritage.com.au for terms.

Support
-------

Open source under LGPL-3 (with the brand-attribution footer constraint). For commercial whitelabel licensing, implementation services, or tier-1 support contact https://www.erpheritage.com.au/.

Issues raised on the public repository are taken seriously and fixes ship on the public branch.

Licence
-------

This module is published under the **LGPL-3** licence with one publisher requirement: the brand-attribution footer ``Made with love from Melbourne, Australia by ERP Heritage`` must remain intact and renders on every PDF. Tampering with the brand line fails the SHA-256 integrity check and the suite refuses to operate. Whitelabel licences are available from the publisher.
