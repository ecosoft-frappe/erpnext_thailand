# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import CustomFunction


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data, None, None, None


def get_columns():
	return [
		{
			"label": _("Tax Address"),
			"fieldname": "company_tax_address",
			"fieldtype": "Link",
			"options": "Address",
			"width": 0,
		},
		{
			"label": _("Report Date"),
			"fieldname": "report_date",
			"fieldtype": "Date",
			"width": 0,
		},
		{
			"label": _("Number"),
			"fieldname": "name",
			"fieldtype": "Data",
			"width": 0,
		},
		{
			"label": _("Supplier"),
			"fieldname": "party_name",
			"fieldtype": "Data",
			"width": 0,
		},
		{
			"label": _("Tax ID"),
			"fieldname": "tax_id",
			"fieldtype": "Data",
			"width": 0,
		},
		{
			"label": _("Branch"),
			"fieldname": "branch_code",
			"fieldtype": "Data",
			"width": 0,
		},
		{
			"label": _("Supplier Address"),
			"fieldname": "supplier_address",
			"fieldtype": "Data",
			"width": 0,
		},
		{
			"label": _("Tax Base"),
			"fieldname": "tax_base",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 0,
		},
		{
			"label": _("Tax Amount"),
			"fieldname": "tax_amount",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 0,
		},
		{
			"label": _("Ref Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 0,
		},
		{
			"label": _("Ref Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 0,
		},
		{
			"label": _("Ref Tax Invoice"),
			"fieldname": "tax_invoice",
			"fieldtype": "Link",
			"options": "Purchase Tax Invoice",
			"width": 0,
		},
	]


def get_data(filters):

	tinv = frappe.qb.DocType("Purchase Tax Invoice")
	sup = frappe.qb.DocType("Supplier")
	addr = frappe.qb.DocType("Address")
	addr_company = addr.as_("company_address") 
	round = CustomFunction("round", ["value", "digit"])
	coalesce = CustomFunction("coalesce", ["value1", "value2"])
	month = CustomFunction("month", ["date"])
	year = CustomFunction("year", ["date"])
	concat_ws = CustomFunction("concat_ws", ["separator", "1", "2", "3", "4", "5", "6"])

	query = (
		frappe.qb.from_(tinv)
		.left_join(sup)
		.on(sup.name == tinv.party)
		.left_join(addr)
		.on(addr.name == sup.supplier_primary_address)
		.left_join(addr_company)  
		.on(addr_company.name == tinv.company_tax_address) 
		.select(
			tinv.company_tax_address.as_("company_tax_address"),
			tinv.report_date.as_("report_date"),
			addr_company.address_line1.as_("company_address_line1"), 
			addr_company.address_line2.as_("company_address_line2"),
            addr_company.city.as_("company_city"),
            addr_company.county.as_("company_county"),
            addr_company.state.as_("company_state"),
            addr_company.pincode.as_("company_pincode"),
            addr_company.branch_code.as_("company_branch_code"),
			coalesce(tinv.number, tinv.name).as_("name"),
			sup.supplier_name.as_("party_name"),
			sup.tax_id.as_("tax_id"),
			sup.branch_code.as_("branch_code"),
			concat_ws(
				" ",
				addr.address_line1,
				addr.address_line2,
				addr.city,
				addr.county,
				addr.state,
				addr.pincode,
			).as_("supplier_address"),
			round(tinv.tax_base, 2).as_("tax_base"),
			round(tinv.tax_amount, 2).as_("tax_amount"),
			tinv.voucher_type.as_("voucher_type"),
			tinv.voucher_no.as_("voucher_no"),
			tinv.name.as_("tax_invoice"),
			tinv.company.as_("company"),
		)
		.where(tinv.docstatus == 1)
		.orderby(tinv.report_date)
	)

	if filters.get("filter_based_on") == "Fiscal Year":
		query = query.where(month(tinv.report_date) == filters.get("month"))
		query = query.where(year(tinv.report_date) == filters.get("year"))

	if filters.get("filter_based_on") == "Date Range":
		query = query.where(tinv.report_date >= filters.get("start_date"))
		query = query.where(tinv.report_date <= filters.get("end_date"))

	if filters.get("company_tax_address"):
		query = query.where(tinv.company_tax_address == filters.get("company_tax_address"))

	result = query.run(as_dict=True)

	return result
