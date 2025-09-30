frappe.ui.form.on("Journal Entry", {
	setup(frm) {
		frm.add_fetch("customer", "customer_name", "party_name");
		frm.add_fetch("supplier", "supplier_name", "party_name");
	},
	refresh(frm) {
		frm.set_query("company_tax_address", function () {
			return {
				filters: {
					is_your_company_address: true,
				},
			};
		});
		frm.set_query("company_tax_address", "tax_invoice_details", () => {
			return {
				filters: {
					is_your_company_address: true,
				},
			};
		});
	},
});

frappe.ui.form.on("Journal Entry Tax Invoice Detail", {
	customer(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.customer) {
			frappe.model.set_value(cdt, cdn, "supplier", "");
		}
	},
	supplier(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.supplier) {
			frappe.model.set_value(cdt, cdn, "customer", "");
		}
	},
});

frappe.ui.form.on("Journal Entry Account", {
	customer(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.customer) {
			frappe.model.set_value(cdt, cdn, "supplier", "");
		}
	},
	supplier(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.supplier) {
			frappe.model.set_value(cdt, cdn, "customer", "");
		}
	},
	account(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "petty_cash_holder", "");
		frappe.model.set_value(cdt, cdn, "petty_cash_holder_name", "");
	}
});
