```js
/** @odoo-module **/

/**
 * MPS Vendor Demand – frontend helpers
 *
 * Registers a client-side action that can be used to navigate from the
 * native MPS Owl client action directly to the Vendor Demand analysis
 * without leaving the planning workspace.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

class MpsVendorDemandButton extends Component {
    setup() {
        this.action = useService("action");
    }

    openVendorDemand() {
        this.action.doAction("mrp_mps_vendor_demand.action_mps_vendor_demand");
    }
}

MpsVendorDemandButton.template = "mrp_mps_vendor_demand.VendorDemandButton";

// Register as a systray item so it's easily reachable from within the MPS view
registry.category("actions").add(
    "mps_vendor_demand_open",
    MpsVendorDemandButton
);
```