// Copyright (c) 2026, Ecosoft and contributors
// For license information, please see license.txt

frappe.ui.form.on("eTax Document Type", {
	setup(frm) {
		frm.set_query("print_format", () => ({
			filters: {
				doc_type:
					frm.doc.applies_to === "Payment Entry" ? "Payment Entry" : "Sales Invoice",
				disabled: 0,
			},
		}));
	},
});
