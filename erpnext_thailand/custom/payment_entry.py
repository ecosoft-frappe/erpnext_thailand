import json
from ast import literal_eval

import frappe
import pandas as pd
from frappe import _
from erpnext_thailand.custom.custom_api import get_thai_tax_settings

REF_DOCTYPES = ["Purchase Invoice", "Expense Claim", "Journal Entry"]


@frappe.whitelist()
def test_require_withholding_tax(doc):
	"""Check if any of the payment references has withholding tax type"""
	pay = json.loads(doc)
	for d in pay.get("references"):
		# Purchase Invoice
		if d.get("reference_doctype") in ["Purchase Invoice", "Sales Invoice"]:
			ref_doc = frappe.get_doc(d.get("reference_doctype"), d.get("reference_name"))
			for item in ref_doc.items:
				if item.withholding_tax_type:
					return True
	return False


@frappe.whitelist()
def get_withholding_tax_from_type(filters, doc):
	filters = literal_eval(filters)
	pay = frappe._dict(json.loads(doc))
	wht = frappe.get_doc("Withholding Tax Type", filters["wht_type"])
	company = frappe.get_doc("Company", pay.company)
	base_amount = 0
	for ref in pay.references:
		if ref.get("reference_doctype") not in [
			"Sales Invoice",
			"Purchase Invoice",
			"Expense Claim",
			"Journal Entry",
		]:
			return
		if not ref.get("allocated_amount") or not ref.get("total_amount"):
			continue
		# Find gl entry of ref doc that has undue amount
		gl_entries = frappe.db.get_all(
			"GL Entry",
			filters={
				"voucher_type": ref["reference_doctype"],
				"voucher_no": ref["reference_name"],
			},
			fields=[
				"name",
				"account",
				"debit",
				"credit",
			],
		)
		for gl in gl_entries:
			credit = gl["credit"]
			debit = gl["debit"]
			alloc_percent = ref["allocated_amount"] / ref["total_amount"]
			root_type = frappe.get_cached_value("Account", gl["account"], "root_type")
			account_type = frappe.get_cached_value("Account", gl["account"], "account_type")
			valid_types = (
				"Asset Received But Not Billed",
				"Chargeable",
				"Capital Work in Progress",
				"Cost of Goods Sold",
				"Current Asset",
				"Direct Expense",
				"Direct Income",
				"Expense Account",
				"Expenses Included In Asset Valuation",
				"Expenses Included In Valuation",
				"Fixed Asset",
				"Income Account",
				"Indirect Expense",
				"Indirect Income",
				"Service Received But Not Billed",
				"Temporary"
			)
			if root_type in ["Asset", "Income", "Expense"] and account_type in valid_types:
				base_amount += alloc_percent * (credit - debit)
	if not base_amount:
		frappe.throw(_("The accounts eligible for withholding tax deduction were not found."))
	sign = -1 if pay.party_type == "Receive" else 1
	return {
		"withholding_tax_type": wht.name,
		"account": wht.get_account(pay.company),
		"cost_center": company.cost_center,
		"base": base_amount * sign,
		"rate": wht.percent,
		"amount": wht.percent / 100 * base_amount * sign,
	}


@frappe.whitelist()
def get_withholding_tax_from_docs_items(doc):
	pay = frappe._dict(json.loads(doc))
	company = frappe.get_doc("Company", pay.company)
	result = []
	wht_types = frappe.get_all(
		"Withholding Tax Type",
		filters=[
        	["Withholding Tax Type Account", "company", "=", company.name]
        ],
		fields=["name", "percent", "`tabWithholding Tax Type Account`.account"],
		as_list=True,
	)
	wht_rates = frappe._dict({x[0]: {"percent": x[1], "account": x[2]} for x in wht_types})
	for ref in pay.references:
		# For Purchase Invoice, Sales Invoice
		ref_doctype = ref.get("reference_doctype")
		if ref_doctype in ["Purchase Invoice", "Sales Invoice"]:
			if not ref.get("allocated_amount") or not ref.get("total_amount"):
				continue
			sign = -1 if pay.payment_type == "Pay" else 1
			ref_doc = frappe.get_doc(ref_doctype, ref.get("reference_name"))
			for item in ref_doc.items:
				wht_type = get_wht_type(ref_doctype, pay, item)
				if wht_type:
					result.append(
						{
							"withholding_tax_type": wht_type,
							"account": wht_rates[wht_type]["account"],
							"cost_center": company.cost_center,
							"base": sign * item.amount,
							"rate": wht_rates[wht_type]["percent"],
							"amount": wht_rates[wht_type]["percent"] / 100 * sign * item.amount,
						}
					)
	# Group by and sum
	df = pd.DataFrame(result)
	group_fields = ["withholding_tax_type", "account", "cost_center", "rate"]
	sum_fields = ["base", "amount"]
	dict_sum_fields = {x: sum for x in sum_fields}
	result = df.groupby(group_fields, as_index=False).aggregate(dict_sum_fields)
	result = result.to_dict(orient="records")
	return result


def get_wht_type(ref_doctype, pay, item):
	item = frappe.get_doc("Item", item.item_code)
	wht_type = None
	if ref_doctype == "Purchase Invoice":
		supplier = frappe.get_cached_doc("Supplier", pay.party)
		if supplier.supplier_type == "Individual":
			wht_type = item.withholding_tax_type_pay_individual
		else:
			wht_type = item.withholding_tax_type_pay_supplier
	if ref_doctype == "Sales Invoice":
		wht_type = item.withholding_tax_type
	return wht_type


@frappe.whitelist()
def make_withholding_tax_cert(filters, doc):
	filters = literal_eval(filters)
	pay = json.loads(doc)
	cert = frappe.new_doc("Withholding Tax Cert")
	cert.supplier = pay.get("party_type") == "Supplier" and pay.get("party") or ""
	if cert.supplier != "":
		supplier = frappe.get_doc("Supplier", cert.supplier)
		cert.supplier_name = supplier and supplier.supplier_name or ""
		cert.supplier_address = supplier and supplier.supplier_primary_address or ""
	cert.voucher_type = "Payment Entry"
	cert.voucher_no = pay.get("name")
	cert.company_address = filters.get("company_address")
	cert.income_tax_form = filters.get("income_tax_form")
	cert.date = filters.get("date")
	for d in pay.get("deductions"):
		base = d.get("withholding_tax_base", 0)
		amount = d.get("amount", 0)
		rate = 0
		wht_type = d.get("withholding_tax_type")
		if wht_type:
			rate = frappe.get_cached_value("Withholding Tax Type", wht_type, "percent")
		cert.append(
			"withholding_tax_items",
			{
				"tax_base": -base,
				"tax_rate": rate,
				"tax_amount": -amount,
			},
		)
	return cert


def reconcile_undue_tax(doc, method):
	""" If bs_reconcile is installed, unreconcile undue tax gls """
	vouchers = [doc.name] + [r.reference_name for r in doc.references]
	reconcile_undue_tax_gls(vouchers, doc.company)


def reconcile_undue_tax_gls(vouchers, company, unreconcile=False):
	""" Only if bs_reconcile app is install, reconcile/unreconcile undue tax gl entries """
	if "bs_reconcile" not in frappe.get_installed_apps():
		return
	try:
		from bs_reconcile.balance_sheet_reconciliation import utils
	except ImportError:
		pass
	tax = get_thai_tax_settings(company)
	undue_taxes = [tax.purchase_tax_account_undue, tax.sales_tax_account_undue]
	gl_entries = utils.get_gl_entries_by_vouchers(vouchers)
	undue_tax_gls = list(filter(lambda x: x.account in undue_taxes, gl_entries))
	if unreconcile:
		utils.unreconcile_gl(undue_tax_gls)
	else:
		utils.reconcile_gl(undue_tax_gls)


def update_sales_billing_outstanding_amount(doc, method):
	# Document: Payment Entry
	total_outstanding_amount = 0
	if not doc.sales_billing:
		return
	bill = frappe.get_doc("Sales Billing", doc.sales_billing)
	for bill_line in bill.sales_billing_line:
		invoice = frappe.get_doc("Sales Invoice", bill_line.sales_invoice)
		bill_line.outstanding_amount = invoice.outstanding_amount
		total_outstanding_amount += invoice.outstanding_amount
	bill.total_outstanding_amount = total_outstanding_amount
	# Status closed
	bill.closed = 0 if bill.total_outstanding_amount else 1
	bill.save()


@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
	from erpnext.accounts.doctype.payment_entry.payment_entry \
     	import get_outstanding_reference_documents as erpnext_get_outstanding
	data = erpnext_get_outstanding(args, validate)
	# Filter by Sales billing / Purchase Billing
	args = frappe._dict(json.loads(args))
	invoices = []
	if args.sales_billing:
		sales_billing = frappe.get_doc("Sales Billing", args.sales_billing)
		invoices = [x.sales_invoice for x in sales_billing.sales_billing_line]
	elif args.purchase_billing:
		purchase_billing = frappe.get_doc("Purchase Billing", args.purchase_billing)
		invoices = [x.purchase_invoice for x in purchase_billing.purchase_billing_line]
	if invoices:
		data = filter(lambda x: x.get("voucher_no") in invoices, data)
	return data
