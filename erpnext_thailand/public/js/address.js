frappe.ui.form.on("Address", {
	refresh(frm) {
		// Add button to use VAT Service
		frm.add_custom_button(__("By Tax ID"), function () {
			const fields = [
				{
					fieldtype: "Data",
					label: __("Tax ID"),
					fieldname: "tax_id",
					reqd: 1,
				},
				{
					fieldtype: "Data",
					label: __("Branch"),
					fieldname: "branch",
					default: "00000",
					reqd: 1,
				},
			];
			frappe.prompt(
				fields,
				function (filters) {
					frm.events.get_address_by_tax_id(frm, filters);
				},
				__("RD VAT Service"),
				__("Get Address")
			);
		}, __("Get Address"));

		// Get Address from zip code
		frm.add_custom_button(__("By Zip Code"), function() {
			frappe.prompt(
				{
					fieldtype: "Data",
					label: __("Zip Code"),
					fieldname: "zip_code",
					reqd: 1
				},
				function(data) {
					frappe.call({
						method: "erpnext_thailand.utils.get_location_by_zip_code",
						args: {
							zip_code: data.zip_code
						},
						callback: function(r) {
							if (r.message.length === 1) {
								// Only one result, set the fields directly
								const location = r.message[0];
								frm.set_value("pincode", location.zip_code);
								frm.set_value("city", location.tambon);
								frm.set_value("county", location.amphur);
								frm.set_value("state", location.province);
							} else if (r.message.length > 1) {
								// Multiple results, prompt the user to select one
								const options = r.message.map(loc => ({
									label: `${loc.zip_code}, ${loc.tambon}, ${loc.amphur}, ${loc.province}`,
									value: loc.id
								}));
								frappe.prompt(
									{
										fieldtype: "Select",
										label: __("Select Location"),
										fieldname: "location_id",
										options: options,
										reqd: 1
									},
									function(selection) {
										const selected_location = r.message.find(loc => loc.id === selection.location_id);
										frm.set_value("pincode", selected_location.zip_code);
										frm.set_value("city", selected_location.tambon);
										frm.set_value("county", selected_location.amphur);
										frm.set_value("state", selected_location.province);
									},
									__("Select Location"),
									__("Select")
								);
							} else {
								frappe.msgprint(__("No location found for the provided zip code."));
							}
						}
					});
				},
				__("Enter Zip Code"),
				__("Get Location")
			);
		}, __("Get Address"));
	},

	get_address_by_tax_id: function (frm, filters) {
		return frappe.call({
			method: "erpnext_thailand.utils.get_address_by_tax_id",
			args: {
				tax_id: filters.tax_id,
				branch: filters.branch,
			},
			callback: function (r) {
				cur_frm.set_value("address_title", r.message["name"]);
				cur_frm.set_value("address_line1", r.message["address_line1"]);
				cur_frm.set_value("city", r.message["city"]);
				cur_frm.set_value("county", r.message["county"]);
				cur_frm.set_value("state", r.message["state"]);
				cur_frm.set_value("pincode", r.message["pincode"]);
				cur_frm.set_value("tax_id", filters.tax_id);
				cur_frm.set_value("branch_code", filters.branch);
				cur_frm.set_value("update_tax_branch", 1);
			},
		});
	},
});

