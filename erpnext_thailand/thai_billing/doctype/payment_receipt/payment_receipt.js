// Copyright (c) 2024, FLO and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Receipt", {
	refresh(frm) {
		frm.set_query("sales_billing", () => ({
			filters: {
				customer: frm.doc.customer,
				docstatus: 1,
			},
		}));
	},

	customer(frm) {
		frm.set_value("sales_billing", "");
	},
});
