// Loaded after the list view settings of ERPNext (doctype_list_js)
["Sales Invoice", "Payment Entry"].forEach((doctype) => {
	const settings = (frappe.listview_settings[doctype] = frappe.listview_settings[doctype] || {});
	if (settings.etax_action_added) return;
	settings.etax_action_added = true;
	settings.formatters = settings.formatters || {};
	settings.formatters.etax_status = (value) =>
		erpnext_thailand.etax.status_indicator(value, true);
	const onload = settings.onload;
	settings.onload = function (listview) {
		onload && onload.call(this, listview);
		listview.page.add_action_item(__("Sign e-Tax"), () =>
			erpnext_thailand.etax.sign_list_dialog(listview)
		);
	};
});
