# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import Case, CustomFunction


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
			"hidden": 1,
		},
		{
			"label": _("Report Date"),
			"fieldname": "report_date",
			"fieldtype": "Date",
			"width": 0,
			"hidden": 1,
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 0,
		},
		{
			"label": _("Number"),
			"fieldname": "name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Customer"),
			"fieldname": "party_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Tax ID"),
			"fieldname": "tax_id",
			"fieldtype": "Data",
			"width": 120,
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
			"label": _("Tax Percent"),
			"fieldname": "tax_percent",
			"fieldtype": "Percent",
			"width": 0,
			"hidden": 0,
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
			"width": 200,
		},
	]


def get_data(filters):

	tinv = frappe.qb.DocType("Sales Tax Invoice")
	cust = frappe.qb.DocType("Customer")
	addr = frappe.qb.DocType("Address")
	comp = frappe.qb.DocType("Company")
	addr_company = addr.as_("company_address")
	si = frappe.qb.DocType("Sales Invoice")
	addr_invoice = addr.as_("invoice_address")
	round = CustomFunction("round", ["value", "digit"])
	month = CustomFunction("month", ["date"])
	year = CustomFunction("year", ["date"])
	concat = CustomFunction("concat", ["1", "2"])

	query = (
		frappe.qb.from_(tinv)
		.left_join(cust)
		.on(cust.name == tinv.party)
		.left_join(comp)
		.on(comp.name == tinv.company)
		.left_join(addr_company)
		.on(addr_company.name == tinv.company_tax_address)
		.left_join(si)
		.on((si.name == tinv.voucher_no) & (tinv.voucher_type == 'Sales Invoice'))
		.left_join(addr_invoice)
		.on(addr_invoice.name == si.customer_address)
		.select(
			tinv.company_tax_address.as_("company_tax_address"),
			addr_company.address_line1.as_("company_address_line1"),
			addr_company.address_line2.as_("company_address_line2"),
			addr_company.city.as_("company_city"),
			addr_company.county.as_("company_county"),
			addr_company.state.as_("company_state"),
			addr_company.pincode.as_("company_pincode"),
			addr_company.branch_code.as_("company_branch_code"),
			tinv.report_date.as_("report_date"),
			tinv.date.as_("date"),
			Case()
			.when(tinv.docstatus == 1, tinv.name)
			.else_(concat(tinv.name, " (CANCEL)"))
			.as_("name"),
			tinv.party_name.as_("party_name"),
			cust.tax_id.as_("tax_id"),
			Case().when(tinv.docstatus == 1, round(tinv.tax_base, 2)).else_(0).as_("tax_base"),
			Case()
			.when(tinv.docstatus == 1, round(tinv.tax_amount, 2))
			.else_(0)
			.as_("tax_amount"),
			tinv.tax_percent.as_("tax_percent"),
			tinv.voucher_type.as_("voucher_type"),
			tinv.voucher_no.as_("voucher_no"),
			comp.company_name.as_("company_name"),
			comp.tax_id.as_("company_tax_id"),
			addr_invoice.branch_code.as_("branch_code")
		)
		.where(tinv.docstatus.isin([1, 2]))
		.orderby(tinv.name)
	)

	if filters.get("filter_based_on") == "Fiscal Year":
		query = query.where(month(tinv.report_date) == filters.get("month"))
		query = query.where(year(tinv.report_date) == filters.get("year"))

	if filters.get("filter_based_on") == "Date Range":
		query = query.where(tinv.report_date >= filters.get("start_date"))
		query = query.where(tinv.report_date <= filters.get("end_date"))

	if filters.get("tax_percent"):
		query = query.where(tinv.tax_percent == filters.get("tax_percent"))

	if filters.get("company_tax_address"):
		query = query.where(tinv.company_tax_address == filters.get("company_tax_address"))

	result = query.run(as_dict=True)

	return result
