/** @odoo-module **/
// ERP Heritage Logistics: Freight Forwarding onboarding tour.
// Walks the operator from the freight job list through the lifecycle:
// draft -> booked -> in transit -> at destination -> delivered -> closed.
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("eh_log_freight_tour", {
    url: "/odoo",
    steps: () => [
        {
            content: "Open the Logistics app.",
            trigger: ".o_app:contains('Logistics'), .o_navbar_apps_menu",
            run: "click",
        },
        {
            content: "Navigate to Operations > Freight Jobs.",
            trigger: ".o_menu_sections a:contains('Operations'), .o_menu_brand",
        },
        {
            content: "This is the Freight Jobs list. Records are auto-spawned by confirming a logistics quotation; the manager can also create one directly.",
            trigger: ".o_list_view, .o_kanban_view",
        },
        {
            content: "Open any open freight job to see the snapshot hero.",
            trigger: ".o_data_row:first, .o_kanban_record:first",
            run: "click",
        },
        {
            content: "The dark navy hero gives you Origin > Mode pill > Destination at a glance, plus 4 KPI tiles for customer, ETD, ETA, and margin.",
            trigger: ".o_eh_log_snapshot",
        },
        {
            content: "Confirm the booking once the carrier has the slot. State moves draft > booked.",
            trigger: "button[name='action_book']",
        },
        {
            content: "Set in transit when the cargo departs. State moves booked > in_transit.",
            trigger: "button[name='action_set_in_transit']",
        },
        {
            content: "When the cargo lands, mark it at destination. The customs team gets the trigger to clear.",
            trigger: "button[name='action_set_at_destination']",
        },
        {
            content: "Mark delivered after POD is signed. Last-mile / transport closes its leg here.",
            trigger: "button[name='action_set_delivered']",
        },
        {
            content: "Manager closes the file when all costs and revenue are reconciled. Closed is terminal.",
            trigger: "button[name='action_close']",
        },
        {
            content: "Open the cost and revenue ledger pages on the notebook to see the planned-vs-actual margin.",
            trigger: ".o_notebook .nav-link:contains('Cost'), .o_notebook .nav-link:contains('Revenue')",
        },
    ],
});
