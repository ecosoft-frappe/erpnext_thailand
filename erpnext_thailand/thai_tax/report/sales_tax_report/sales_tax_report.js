// Copyright (c) 2023, Kitti U. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Tax Report"] = {
	filters: [
		{
			fieldname: "filter_based_on",
			label: __("Filter Based On"),
			fieldtype: "Select",
			options: ["Fiscal Year", "Date Range"],
			default: ["Fiscal Year"],
			reqd: 1,
			on_change: function () {
				let filter_based_on = frappe.query_report.get_filter_value("filter_based_on");
				frappe.query_report.toggle_filter_display(
					"year",
					filter_based_on === "Date Range"
				);
				frappe.query_report.toggle_filter_display(
					"month",
					filter_based_on === "Date Range"
				);
				frappe.query_report.toggle_filter_display(
					"start_date",
					filter_based_on === "Fiscal Year"
				);
				frappe.query_report.toggle_filter_display(
					"end_date",
					filter_based_on === "Fiscal Year"
				);

				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
		},
		{
			fieldname: "start_date",
			label: __("Start Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "end_date",
			label: __("End Date"),
			fieldtype: "Date",
		},
        {
            fieldname: "tax_percent",
            label: __("Tax Percent"),
            fieldtype: "Select",
            options: get_percent_options()
        },
		{
			fieldname: "company_tax_address",
			label: __("Company Address"),
			fieldtype: "Link",
			options: "Address",
			get_query: () => {
				return {
					filters: {
						is_your_company_address: 1,
					},
				};
			},
		},
	],
};

function get_percent_options() {
	let options = [""];
	frappe.db.get_list("Sales Tax Invoice", { fields: ["tax_percent"], distinct: 1, order_by: "tax_percent" }).then((res) => {
		res.forEach((dimension) => {
			options.push(dimension.tax_percent + "%");
		});
	});
	return options;
}
