frappe.ui.form.on("Currency Exchange Settings", {
	refresh(frm) {
		if (frm.doc.service_provider === "Bank of Thailand") {
			frm.toggle_display("use_http", false);
		}
	},

	set_table_parameters: function (frm) {
		// Clear existing rows
		frm.clear_table("req_params");

		// Example data to add
		const set_parameters = [
			{ key: "from_currency", value: "{from_currency}" },
			{ key: "to_currency", value: "{to_currency}" },
			{ key: "transaction_date", value: "{transaction_date}" }
		];

		// Add new rows
		set_parameters.forEach(data => {
			const child = frm.add_child("req_params");
			frappe.model.set_value(child.doctype, child.name, "key", data.key);
			frappe.model.set_value(child.doctype, child.name, "value", data.value);
		});

		// Refresh the child table to show changes
		frm.refresh_field("req_params");
	},

	set_table_result_key: function (frm) {
		// Clear existing rows
		frm.clear_table("result_key");

		// Example data to add
		const set_result_key = [
			{ key: "message" },
			{ key: "rates" },
			{ key: "{to_currency}" }
		];

		// Add new rows
		set_result_key.forEach(data => {
			const child = frm.add_child("result_key");
			frappe.model.set_value(child.doctype, child.name, "key", data.key);
		});

		// Refresh the child table to show changes
		frm.refresh_field("result_key");
	},

	service_provider: function (frm) {
		if (frm.doc.service_provider === "Bank of Thailand") {
			const base_url = window.location.origin
			frm.set_value("api_endpoint", `${base_url}/api/v2/method/erpnext_thailand.custom.currency_exchange_bot_api.get_api_currency_exchange`);
			frm.set_value("url", null)
			frm.toggle_display("use_http", false);
			frm.events.set_table_parameters(frm);
			frm.events.set_table_result_key(frm);
        } else {
			frm.set_value("client_id", null);
            frm.toggle_display("use_http", true);
        }
    }
});
