// Copyright (c) 2023, Kitti U. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Withholding Tax Type", {
	setup: function (frm) {
		frm.set_query("account", function () {
			return {
				filters: { company: frm.doc.company },
			};
		});
	},

	refresh: function (frm) {
		if (frm.doc.name === "Auto" && !frappe.boot.developer_mode) {
			// make the document read-only
			frm.disable_form();
		} else {
			frm.enable_save();
		}
	},

	company(frm) {
		frm.set_value("account", "");
	},
});
