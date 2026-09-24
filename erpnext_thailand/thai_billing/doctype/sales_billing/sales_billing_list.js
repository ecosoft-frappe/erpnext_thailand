frappe.listview_settings["Sales Billing"] = {
	add_fields: ["closed"],
	get_indicator: function (doc) {
		if (doc.closed) {
			return [__("Closed"), "red", "closed,=,1"];
		} else {
			return [__("Open"), "green", "closed,=,0"];
		}
	},
};
