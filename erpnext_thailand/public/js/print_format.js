frappe.provide("erpnext_thailand.print");

erpnext_thailand.print.print_pdf = function(doc) {
	// Fetch default print formats for the given doctype and docname
	frappe.call({
		method: "erpnext_thailand.custom.print_format.get_print_formats",
		args: {
			doctype: doc.doctype,
			docname: doc.name
		},
		callback: function(r) {
			if (r.message) {
				let { print_formats, default_format, default_copies } = r.message;
				// Create a dialog to select print format
				let d = new frappe.ui.Dialog({
					title: __("Select Print Format"),
					fields: [
						{
							label: __("Print Format"),
							fieldname: "print_format",
							fieldtype: "Select",
							options: print_formats,
							reqd: 1,
							default: default_format
						}
					],
					primary_action_label: __("Print PDF"),
					primary_action(values) {
						let print_format = values.print_format;
						const w = window.open(
							"/api/method/erpnext_thailand.custom.print_format.download_print_pdf?" +
								"doctype=" +
								encodeURIComponent(doc.doctype) +
								"&name=" +
								encodeURIComponent(doc.name) +
								"&format=" +
								encodeURIComponent(print_format)
								// Following are params for future imple.
								// "&no_letterhead=" +
								// (with_letterhead ? "0" : "1") +
								// "&letterhead=" +
								// encodeURIComponent(letterhead) +
								// "&options=" +
								// encodeURIComponent(pdf_options)
								// --
							);
						if (!w) {
							frappe.msgprint(__("Please enable pop-ups"));
						}
						d.hide();
					}
				});
				d.show();
			}
		}
	});
};
