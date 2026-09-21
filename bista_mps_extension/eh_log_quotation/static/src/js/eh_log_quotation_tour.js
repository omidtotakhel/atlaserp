/** @odoo-module **/
// ERP Heritage Logistics: Quotation onboarding tour.
// Walks an operator through creating a logistics-flagged sale order, applying
// a charge template, and confirming - which spawns the freight job.
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("eh_log_quotation_tour", {
    url: "/odoo/sales",
    steps: () => [
        {
            content: "Open the Quotations / Orders list to create a new logistics quotation.",
            trigger: "button.o-kanban-button-new, .o_list_button_add",
            run: "click",
        },
        {
            content: "Pick the customer. KYC and credit status surface live in the Logistics tab.",
            trigger: "[name='partner_id'] input",
        },
        {
            content: "Tick the Logistics box - this turns the quote into a logistics quote.",
            trigger: "[name='eh_log_is_logistics'] input",
        },
        {
            content: "Open the Logistics tab to set the lane, mode, direction, and charge template.",
            trigger: ".o_notebook .nav-link:contains('Logistics')",
            run: "click",
        },
        {
            content: "Pick the mode (Sea / Air / Road / Rail / Multimodal). The radio widget shows them all at once.",
            trigger: "[name='eh_log_mode']",
        },
        {
            content: "Pick the direction. Import / Export / Cross Trade.",
            trigger: "[name='eh_log_direction']",
        },
        {
            content: "Select a charge template for this lane. Lines pre-fill with the template's defaults.",
            trigger: "[name='eh_log_charge_template_id'] input",
        },
        {
            content: "Save the quotation. Margin / KYC / credit guards run on save.",
            trigger: ".o_form_button_save, button.o_form_button_save",
        },
        {
            content: "Confirm the quotation. A freight job is auto-spawned with the matching mode and lane.",
            trigger: "button[name='action_confirm']",
        },
        {
            content: "Open the Freight Jobs smart button to see the spawned job. From here on the operations team takes over.",
            trigger: "button[name='action_view_eh_log_freight_jobs']",
        },
    ],
});
