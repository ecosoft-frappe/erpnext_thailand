# Copyright (c) 2026, Ecosoft and contributors
# For license information, please see license.txt
"""Connector to the Frappe e-Tax service (etax_inet app).

Sales Invoices (invoice, credit note, debit note) and customer Payment Entries
(receipts) are sent to the e-Tax server for signing, then the signed PDF and
XML are attached back to the document.
"""

import base64
import calendar
import json
import re
from collections import defaultdict

import frappe
import requests
from frappe import _
from frappe.utils import add_months, flt, get_url, getdate, today

SIGN_ROUTE = "/api/method/etax_inet.api.etax.sign_etax_document"
STATUS_ROUTE = "/api/resource/INET ETax Document"
STATUS_FIELDS = [
	"status",
	"transaction_code",
	"error_code",
	"error_message",
	"pdf_url",
	"xml_url",
]
ETAX_DOCTYPES = ("Sales Invoice", "Payment Entry")
ETAX_STATUSES = ("Processing", "Success", "Error", "Replaced")
SIGNED_STATUSES = ("Processing", "Success", "Replaced")
RESULT_FIELDS = (
	"etax_status",
	"etax_transaction_code",
	"etax_error_code",
	"etax_error_message",
)
CREDIT_NOTE_CODE = "81"
# 380 (ใบแจ้งหนี้) is not a tax invoice, it has no replacement or credit/debit note
NON_TAX_INVOICE_CODES = ("380",)
DEBIT_NOTE_CODE = "80"
# ใบรับ (ใบเสร็จรับเงิน), a receipt that is not a tax invoice
RECEIPT_CODE = "T01"
# form_type of etax_inet: "frappe" lets the e-Tax server render its own
# print format, other values mean the source system sends the rendered PDF.
FORM_TYPE_ETAX_SERVER = "frappe"
FORM_TYPE_ERPNEXT = "erpnext"
TIMEOUT = 60
# Each document takes seconds (PDF and e-Tax server), more documents are signed
# in background to stay within the request timeout
SIGN_NOW_LIMIT = 10
# integration_request_service of the e-Tax request logs
INTEGRATION_SERVICE = "e-Tax"
# Roles that read the e-Tax request logs, but not those of other integrations
ETAX_LOG_ROLES = ("Accounts Manager", "Accounts User")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def get_etax_connection(company):
	"""Return the enabled eTax Connection of the company, or throw."""
	name = frappe.db.get_value("eTax Connection", {"company": company, "enabled": 1})
	if not name:
		frappe.throw(
			_("e-Tax is not enabled for company {0}. Please set up eTax Connection.").format(
				company
			)
		)
	return frappe.get_cached_doc("eTax Connection", name)


@frappe.whitelist()
def is_etax_enabled(company: str):
	return bool(frappe.db.exists("eTax Connection", {"company": company, "enabled": 1}))


def get_auth_header(connection):
	return {
		"Authorization": f"token {connection.api_key}:{connection.get_password('api_secret')}"
	}


def get_applies_to(doc):
	"""Return the eTax Document Type 'Applies To' matching the document"""
	if doc.doctype == "Payment Entry":
		return "Payment Entry"
	if doc.is_return:
		return "Credit Note"
	if doc.is_debit_note:
		return "Debit Note"
	return "Sales Invoice"


def get_adjustment_doctype_code(doc):
	"""Return the document type code of a credit/debit note, else None"""
	if doc.doctype != "Sales Invoice":
		return None
	if doc.is_return:
		return CREDIT_NOTE_CODE
	if doc.is_debit_note:
		return DEBIT_NOTE_CODE
	return None


def get_reference_doc(doc):
	"""Return the document this one adjusts (credit/debit note) or replaces

	An amendment of a document that was not signed is a new document, not a replacement.
	"""
	if doc.doctype == "Sales Invoice" and doc.return_against:
		return frappe.get_doc("Sales Invoice", doc.return_against)
	if is_replacement(doc):
		return frappe.get_doc(doc.doctype, doc.amended_from)
	return None


def is_replacement(doc):
	"""An amended document whose original was signed is an e-Tax replacement"""
	return bool(
		doc.amended_from
		and frappe.db.get_value(doc.doctype, doc.amended_from, "etax_status")
		in ("Success", "Replaced")
	)


def get_purpose_codes(purpose_code):
	return frappe.get_all(
		"eTax Purpose Code Applicable",
		filters={"parent": purpose_code, "parenttype": "eTax Purpose Code"},
		pluck="document_type_code",
	)


def has_purpose(doc):
	return bool((doc.etax_purpose_code or "").strip() and (doc.etax_purpose or "").strip())


# ---------------------------------------------------------------------------
# Document events
# ---------------------------------------------------------------------------


def validate_etax(doc, method=None):
	"""Reset the e-Tax result on a new (i.e., amended) document, and check its purpose"""
	if doc.is_new():
		# Amending in the UI copies no_copy fields
		doc.update({field: None for field in RESULT_FIELDS})
		# A replacement keeps the document type of the signed original
		if not is_replacement(doc):
			doc.update({"etax_document_type": None, "etax_document_type_code": None})
	if not doc.get("etax_purpose_code"):
		return
	code = get_adjustment_doctype_code(doc)
	if code and code not in get_purpose_codes(doc.etax_purpose_code):
		frappe.throw(
			_("e-Tax Purpose Code {0} cannot be used with document type code {1}.").format(
				doc.etax_purpose_code, code
			)
		)
	# The form sets the reason on change, this covers the purpose code set by code
	if not (doc.etax_purpose or "").strip():
		doc.etax_purpose = frappe.db.get_value(
			"eTax Purpose Code", doc.etax_purpose_code, "reason"
		)


def validate_update_after_submit(doc, method=None):
	"""The purpose of a submitted document can be set until it is signed"""
	changed = any(doc.has_value_changed(f) for f in ("etax_purpose_code", "etax_purpose"))
	if not changed:
		return
	if doc.etax_status in SIGNED_STATUSES:
		frappe.throw(_("The e-Tax purpose cannot be changed after signing e-Tax."))
	validate_etax(doc)


def validate_cancel(doc, method=None):
	"""A signed document can only be cancelled through Create Replacement"""
	if (
		doc.get("etax_status") in ("Processing", "Success") and not doc.flags.etax_replacement
	):
		if doc.doctype == "Payment Entry":
			frappe.throw(
				_(
					"{0} has already been signed as e-Tax. Use Create Replacement to correct it."
				).format(doc.name)
			)
		frappe.throw(
			_(
				"{0} has already been signed as e-Tax. Use Create Replacement to correct it,"
				" or issue a Credit Note instead."
			).format(doc.name)
		)


# ---------------------------------------------------------------------------
# Validation before signing
# ---------------------------------------------------------------------------


def validate_before_sign(doc, etax_doctype):
	if doc.doctype not in ETAX_DOCTYPES:
		frappe.throw(_("e-Tax is not supported for {0}").format(doc.doctype))
	if doc.docstatus != 1:
		frappe.throw(_("{0}: must be submitted before signing e-Tax").format(doc.name))
	if doc.doctype == "Payment Entry" and not (
		doc.payment_type == "Receive" and doc.party_type == "Customer"
	):
		frappe.throw(_("{0}: e-Tax is only available for customer receipts").format(doc.name))
	if doc.etax_status in SIGNED_STATUSES:
		frappe.throw(_("{0}: e-Tax status is already {1}").format(doc.name, doc.etax_status))

	connection = get_etax_connection(doc.company)
	seller_tax_id = get_seller_tax_id(doc)
	if not seller_tax_id:
		frappe.throw(_("Company {0} does not have a Tax ID configured.").format(doc.company))
	if not re.fullmatch(r"\d{13}", seller_tax_id):
		frappe.throw(
			_("Tax ID {0} of company {1} must be 13 digits.").format(seller_tax_id, doc.company)
		)
	customer = get_customer(doc)
	buyer_tax_id, buyer_branch = get_buyer_tax_info(doc)
	if not buyer_tax_id:
		frappe.throw(
			_("Cannot sign e-Tax. Please fill in Tax ID for customer {0}.").format(customer)
		)
	if not re.fullmatch(r"\d{13}", buyer_tax_id):
		frappe.throw(
			_("Cannot sign e-Tax. Tax ID {0} of customer {1} must be 13 digits.").format(
				buyer_tax_id, customer
			)
		)
	if buyer_branch and not re.fullmatch(r"\d{5}", buyer_branch):
		frappe.throw(
			_("Cannot sign e-Tax. Branch Code {0} of customer {1} must be 5 digits.").format(
				buyer_branch, customer
			)
		)
	# The e-Tax server requires the country of the buyer address
	if not get_customer_address(doc).get("country"):
		frappe.throw(
			_("Cannot sign e-Tax. Please set the address of customer {0}.").format(customer)
		)
	check_etax_email(doc, connection)

	applies_to = get_applies_to(doc)
	if etax_doctype.applies_to != applies_to:
		frappe.throw(
			_("e-Tax Document Type {0} is for {1}, not {2}").format(
				etax_doctype.name, etax_doctype.applies_to, applies_to
			)
		)

	adjustment_code = get_adjustment_doctype_code(doc)
	replacement = is_replacement(doc)
	# VAT of a service is due on payment, the receipt is its tax invoice (T03)
	if has_undue_vat(doc) and etax_doctype.document_type_code not in NON_TAX_INVOICE_CODES:
		if adjustment_code:
			frappe.throw(
				_(
					"{0}: The VAT of this credit or debit note is undue (due on payment), it is"
					" not a tax document and is not sent as e-Tax. The receipt (Payment Entry)"
					" is the tax invoice of the amount paid."
				).format(doc.name)
			)
		frappe.throw(
			_(
				"{0}: The VAT of this document is undue (due on payment), it is not a tax"
				" document. Sign it with document type code {1}, and sign the receipt"
				" (Payment Entry) as the tax invoice."
			).format(doc.name, ", ".join(NON_TAX_INVOICE_CODES))
		)

	if (adjustment_code or replacement) and not has_purpose(doc):
		frappe.throw(
			_(
				"{0}: To send this credit note, debit note or replacement as e-Tax,"
				" select an e-Tax Purpose Code and enter its purpose in the e-Tax tab."
			).format(doc.name)
		)
	if adjustment_code and not doc.return_against:
		frappe.throw(
			_(
				"{0}: A credit or debit note must refer to its invoice (Return Against)"
				" to be sent as e-Tax."
			).format(doc.name)
		)
	if adjustment_code:
		reference = get_reference_doc(doc)
		reference_code = reference and reference.get("etax_document_type_code")
		if reference_code in NON_TAX_INVOICE_CODES:
			frappe.throw(
				_(
					"{0}: Cannot send as e-Tax because {1} was signed with document type"
					" code {2}, which is not a tax invoice."
				).format(doc.name, reference.name, reference_code)
			)
	if replacement:
		original_code = frappe.db.get_value(
			doc.doctype, doc.amended_from, "etax_document_type_code"
		)
		if original_code and original_code != etax_doctype.document_type_code:
			frappe.throw(
				_(
					"A replacement must use the same document type code as the original ({0})."
				).format(original_code)
			)
		if etax_doctype.document_type_code not in get_purpose_codes(doc.etax_purpose_code):
			frappe.throw(
				_("e-Tax Purpose Code {0} cannot be used with document type code {1}.").format(
					doc.etax_purpose_code, etax_doctype.document_type_code
				)
			)

	if doc.doctype == "Sales Invoice":
		for tax in doc.taxes:
			if (
				tax.charge_type != "On Net Total" and flt(tax.tax_amount) and is_vat_row(doc, tax)
			):
				frappe.throw(
					_(
						"{0}: Row {1} of Sales Taxes and Charges is VAT calculated {2}, e-Tax"
						" supports VAT calculated On Net Total only. Add a charge, i.e., shipping"
						" or service charge, as an item line instead."
					).format(doc.name, tax.idx, _(tax.charge_type))
				)
	if doc.doctype == "Sales Invoice" and not get_etax_items(doc):
		frappe.throw(
			_(
				"{0}: no e-Tax line items found. Uncheck Skip e-Tax on at least one item"
				" before signing e-Tax."
			).format(doc.name)
		)
	if (
		doc.doctype == "Payment Entry"
		and etax_doctype.document_type_code != RECEIPT_CODE
		and not get_payment_tax_invoices(doc)
	):
		frappe.throw(
			_(
				"{0}: document type code {1} is a tax invoice, but no VAT is due on this payment"
				" (no Sales Tax Invoice). The VAT was invoiced with the Sales Invoice,"
				" use document type code {2} instead."
			).format(doc.name, etax_doctype.document_type_code, RECEIPT_CODE)
		)
	if doc.doctype == "Payment Entry" and not get_payment_line_items(doc):
		frappe.throw(
			_(
				"{0}: no e-Tax line items found. Add Sales Tax Invoice information"
				" or allocate the payment to a Sales Invoice before signing e-Tax."
			).format(doc.name)
		)


def has_undue_vat(doc):
	"""Sales Invoice with VAT on the undue sales tax account of Thai Tax Settings

	An undue account set the same as the sales tax account is not undue VAT.
	"""
	if doc.doctype != "Sales Invoice":
		return False
	undue_accounts = [
		row.sales_tax_account_undue
		for row in frappe.get_cached_doc("Thai Tax Settings").company_accounts
		if row.company == doc.company
		and row.sales_tax_account_undue
		and row.sales_tax_account_undue != row.sales_tax_account
	]
	return any(
		tax.account_head in undue_accounts and flt(tax.tax_amount) for tax in doc.taxes
	)


def is_etax_email_missing(doc, connection):
	return bool(
		connection.send_email
		and connection.require_email
		and not (get_buyer_email(doc) or "").strip()
	)


def check_etax_email(doc, connection):
	if is_etax_email_missing(doc, connection):
		frappe.throw(
			_("Cannot sign e-Tax. Please fill in e-Tax Email for customer {0}.").format(
				get_customer(doc)
			)
		)


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


def get_customer(doc):
	return doc.customer if doc.doctype == "Sales Invoice" else doc.party


def get_buyer_email(doc):
	return frappe.db.get_value("Customer", get_customer(doc), "email_etax")


def format_dtm(date):
	return date and f"{getdate(date).isoformat()}T00:00:00" or ""


def get_currency(doc):
	"""Lines of Sales Tax Invoices (undue VAT) are in company currency"""
	if doc.doctype == "Sales Invoice":
		return doc.currency
	if get_payment_tax_invoices(doc):
		return frappe.get_cached_value("Company", doc.company, "default_currency")
	return doc.paid_from_account_currency


def get_customer_address(doc):
	"""Billing address of the invoice, a receipt takes the address of its first invoice"""
	from frappe.contacts.doctype.address.address import get_default_address

	name = doc.get("customer_address")
	if not name and doc.doctype == "Payment Entry":
		invoices = [
			ref.reference_name
			for ref in doc.references
			if ref.reference_doctype == "Sales Invoice"
		]
		name = invoices and frappe.db.get_value(
			"Sales Invoice", invoices[0], "customer_address"
		)
	name = name or get_default_address("Customer", get_customer(doc))
	return name and frappe.get_doc("Address", name) or frappe._dict()


def get_buyer_tax_info(doc, address=None):
	"""Return (tax_id, branch_code) of the buyer

	A customer with several branches keeps the tax ID and branch code of each
	branch in its address, the customer's own values are the fallback.
	"""
	address = address or get_customer_address(doc)
	customer = frappe.db.get_value(
		"Customer", get_customer(doc), ["tax_id", "branch_code"], as_dict=True
	)
	tax_id = clean_tax_id(address.get("tax_id") or customer.tax_id)
	branch_code = clean_branch_code(address.get("branch_code") or customer.branch_code)
	return tax_id, branch_code


def clean_tax_id(tax_id):
	"""Tax ID as the 13 digits, i.e., 0-1055-54048-64-1 is typed with dashes"""
	return re.sub(r"[\s-]", "", tax_id or "")


def clean_branch_code(branch_code):
	"""Branch code as 5 digits, i.e., 1 is 00001 and the head office is 00000"""
	branch_code = re.sub(r"[\s-]", "", branch_code or "")
	if branch_code.lower() in ("headoffice", "สำนักงานใหญ่"):
		return "00000"
	return branch_code.zfill(5) if branch_code.isdigit() else branch_code


def get_seller_tax_id(doc):
	return clean_tax_id(frappe.db.get_value("Company", doc.company, "tax_id"))


def get_company_address(doc):
	from erpnext.setup.doctype.company.company import get_default_company_address

	name = doc.get("company_address") or doc.get("company_tax_address")
	name = name or get_default_company_address(doc.company)
	return name and frappe.get_doc("Address", name) or frappe._dict()


def get_document_data(doc):
	"""doc_data for etax_inet.api.etax.sign_etax_document"""
	customer = frappe.get_doc("Customer", get_customer(doc))
	address = get_customer_address(doc)
	company_address = get_company_address(doc)
	country_code = (
		address.country and frappe.db.get_value("Country", address.country, "code") or ""
	)
	reference = get_reference_doc(doc)
	buyer_tax_id, buyer_branch_id = get_buyer_tax_info(doc, address)
	data = {
		"currency_code": get_currency(doc),
		"document_type_code": doc.etax_document_type_code,
		"document_id": doc.name,
		"document_issue_dtm": format_dtm(doc.posting_date),
		"create_purpose_code": doc.etax_purpose_code or "",
		"create_purpose": doc.etax_purpose or "",
		"ref_document_id": reference and reference.name or "",
		"ref_document_issue_dtm": reference and format_dtm(reference.posting_date) or "",
		"ref_document_type_code": reference
		and reference.get("etax_document_type_code")
		or "",
		"seller_branch_id": clean_branch_code(company_address.get("branch_code")) or "00000",
		"source_system": get_url(),
		# The e-Tax server can only email a customer that has an e-Tax Email
		"send_mail": get_etax_connection(doc.company).send_email
		and (customer.get("email_etax") or "").strip()
		and "Y"
		or "N",
		"seller_tax_id": get_seller_tax_id(doc),
		"buyer_name": customer.customer_name,
		"buyer_type": "TXID",
		"buyer_tax_id": buyer_tax_id,
		"buyer_branch_id": buyer_branch_id or "00000",
		"buyer_email": customer.get("email_etax"),
		"buyer_zip": address.get("pincode") or "",
		"buyer_building_name": "",
		"buyer_building_no": "",
		"buyer_address_line1": address.get("address_line1") or "",
		"buyer_address_line2": address.get("address_line2") or "",
		# Thai address: city is the sub-district, county the district, state the province
		"buyer_address_line3": " ".join(
			part
			for part in (address.get("city"), address.get("county"), address.get("state"))
			if part
		),
		"buyer_address_line4": address.get("pincode") or "",
		"buyer_address_line5": "",
		# CityName of the e-Tax XML is the district, i.e., county of a Thai address
		"buyer_city_name": address.get("county") or address.get("city") or "",
		"buyer_country_code": country_code.upper(),
	}
	if doc.doctype == "Sales Invoice":
		lines = get_invoice_line_items(doc)
		original, adjustment, corrected = get_additional_amount(doc, lines)
		data.update(
			{
				"buyer_ref_document": doc.po_no or "",
				"original_amount_untaxed": original,
				# Credit/debit notes send the corrected amount, else the line total
				"final_amount_untaxed": corrected,
				"adjust_amount_untaxed": adjustment,
				"line_item_information": lines,
			}
		)
	else:
		lines = get_payment_line_items(doc)
		data.update(
			{
				"buyer_ref_document": "",
				"original_amount_untaxed": False,
				# The line total (F38) of the receipt, the e-Tax server does not sum the lines
				"final_amount_untaxed": get_etax_untaxed_amount(lines),
				"adjust_amount_untaxed": False,
				"line_item_information": lines,
			}
		)
	return data


def get_etax_untaxed_amount(lines):
	return flt(sum(line["line_base_amount"] for line in lines), 2)


def get_additional_amount(doc, lines=None):
	"""Untaxed amounts of a credit/debit note

	f36_original_total_amount = original
	f40_adjusted_information_amount = adjustment
	f38_line_total_amount = corrected

	Both are the amounts of the e-Tax lines, i.e., without the Skip e-Tax lines,
	so that the original is the amount of the invoice sent as e-Tax.
	"""
	lines = get_invoice_line_items(doc) if lines is None else lines
	if not doc.return_against:
		return (False, False, get_etax_untaxed_amount(lines))
	invoice = frappe.get_doc("Sales Invoice", doc.return_against)
	original = get_etax_untaxed_amount(get_invoice_line_items(invoice))
	adjustment = abs(get_etax_untaxed_amount(lines))
	if doc.is_return:
		return (original, adjustment, flt(original - adjustment, 2))
	return (original, adjustment, flt(original + adjustment, 2))


def get_etax_items(doc):
	"""Priced lines and deductions, i.e., a fully discounted line is still sent"""
	return [
		item
		for item in doc.items
		if not item.get("skip_etax")
		and (get_undiscounted_rate(doc, item) > 0 or flt(item.net_amount) < 0)
	]


def get_undiscounted_rate(doc, item):
	"""Rate before discount, i.e., a rate above the price list has no discount

	A credit/debit note line is the adjusted amount, the price list rate copied
	from the original invoice is not a discount of it.
	"""
	if doc.get("return_against"):
		return abs(flt(item.rate))
	return max(abs(flt(item.price_list_rate)), abs(flt(item.rate)))


def get_tax_detail(tax):
	detail = tax.item_wise_tax_detail
	return json.loads(detail) if isinstance(detail, str) else (detail or {})


def get_sales_tax_accounts(company):
	return [
		account
		for row in frappe.get_cached_doc("Thai Tax Settings").company_accounts
		if row.company == company
		for account in (row.sales_tax_account, row.sales_tax_account_undue)
		if account
	]


def is_vat_row(doc, tax):
	"""A row of Sales Taxes and Charges on a tax account is VAT, the others are
	charges, i.e., shipping or service charge"""
	return frappe.get_cached_value(
		"Account", tax.account_head, "account_type"
	) == "Tax" or tax.account_head in get_sales_tax_accounts(doc.company)


def get_charge_rows(doc):
	return [
		tax
		for tax in doc.taxes
		if flt(tax.tax_amount_after_discount_amount) and not is_vat_row(doc, tax)
	]


def get_row_tax_rate(tax, item):
	"""Rate of the tax row for the item row, as ERPNext calculates it,
	None when the item tax template sets the tax not applicable"""
	item_tax_map = item.item_tax_rate or {}
	if isinstance(item_tax_map, str):
		item_tax_map = json.loads(item_tax_map)
	if tax.account_head not in item_tax_map:
		return flt(tax.rate)
	rate = item_tax_map[tax.account_head]
	return None if rate == "N/A" else flt(rate)


def get_invoice_line_amounts(doc):
	"""Return {row name: (rate, base, tax, has_tax, price_factor)}, signed positive for credit notes

	ERPNext keeps the tax of each 'On Net Total' VAT row per item code in
	company currency. It is converted back to the document currency, split
	between the rows of the item code by net amount x rate of the row (its item
	tax template) and rounded cumulatively
	(per row with Round Tax Amount Row-wise), so the rows add up to the tax
	amount of the document.
	price_factor removes the VAT included in the rate of the row.
	"""
	sign = -1 if doc.is_return else 1
	conversion_rate = flt(doc.conversion_rate) or 1.0
	# ERPNext rounds the tax of each item, the document tax is their sum
	row_wise = frappe.db.get_single_value("Accounts Settings", "round_row_wise_tax")
	groups = defaultdict(list)
	for item in doc.items:
		groups[item.item_code or item.item_name].append(item)
	rates = defaultdict(float)
	taxes = defaultdict(float)
	included = defaultdict(float)
	taxed = set()
	for tax in doc.taxes:
		if tax.charge_type != "On Net Total":
			continue
		is_vat = is_vat_row(doc, tax)
		item_tax = {}
		for key, (__, amount) in get_tax_detail(tax).items():
			# Rows of the same item code may have different item tax templates
			rows = [
				(item, rate)
				for item in groups.get(key) or []
				if (rate := get_row_tax_rate(tax, item)) is not None
			]
			group_tax = sum(flt(item.net_amount) * rate for item, rate in rows)
			for item, rate in rows:
				# A charge included in the rate is also removed from the price
				if tax.included_in_print_rate:
					included[item.name] += rate
				if not is_vat:
					continue
				share = flt(item.net_amount) * rate / group_tax if group_tax else 1.0 / len(rows)
				item_tax[item.name] = flt(amount) / conversion_rate * share
				rates[item.name] += rate
				taxed.add(item.name)
		names = [item.name for item in doc.items if item.name in item_tax]
		cumulative = rounded = 0.0
		for i, name in enumerate(names):
			cumulative += flt(item_tax[name], 2) if row_wise else item_tax[name]
			total = (
				flt(tax.tax_amount_after_discount_amount, 2)
				if i == len(names) - 1
				else flt(cumulative, 2)
			)
			taxes[name] += flt(total - rounded, 2)
			rounded = total
	return {
		item.name: (
			rates[item.name],
			flt(sign * flt(item.net_amount), 2),
			flt(sign * taxes[item.name], 2),
			item.name in taxed,
			1 + included[item.name] / 100,
		)
		for item in doc.items
	}


def get_invoice_line_items(doc):
	"""Lines keep their signed base, tax and total, the receiver sums them as is

	A discount (item or document level) is sent as the line allowance (L27)
	between the undiscounted price before VAT and the line base.
	"""
	line_amounts = get_invoice_line_amounts(doc)
	lines = []
	for item in get_etax_items(doc):
		rate, base, tax, has_tax, price_factor = line_amounts[item.name]
		qty = abs(flt(item.qty))
		price = get_undiscounted_rate(doc, item) / price_factor
		# A negative line (i.e., deposit deduction) is sent as an allowance
		is_allowance = base < 0
		if is_allowance:
			allowance = abs(base)
		else:
			allowance = max(flt(price * qty - base, 2), 0.0)
		price = flt(price, 2)
		lines.append(
			{
				"product_code": item.item_code or "",
				"product_name": item.item_name or item.description,
				"product_price": 0.0 if is_allowance else price,
				"product_quantity": 1 if is_allowance else qty,
				"line_tax_type_code": "VAT" if has_tax else "FRE",
				"line_tax_rate": rate,
				"line_base_amount": base,
				"line_tax_amount": tax,
				"line_allowance_charge_ind": "false" if allowance else "",
				"line_allowance_actual_amount": allowance,
				"line_allowance_actual_currency_code": doc.currency,
				"line_total_amount": flt(base + tax, 2),
			}
		)
	# A charge without VAT (VAT is on the net total), the lines add up to the grand total
	sign = -1 if doc.is_return else 1
	for tax in get_charge_rows(doc):
		base = flt(sign * flt(tax.tax_amount_after_discount_amount), 2)
		is_allowance = base < 0
		lines.append(
			{
				"product_code": "",
				"product_name": tax.description or tax.account_head,
				"product_price": 0.0 if is_allowance else base,
				"product_quantity": 1,
				"line_tax_type_code": "FRE",
				"line_tax_rate": 0.0,
				"line_base_amount": base,
				"line_tax_amount": 0.0,
				"line_allowance_charge_ind": "false" if is_allowance else "",
				"line_allowance_actual_amount": abs(base) if is_allowance else 0.0,
				"line_allowance_actual_currency_code": doc.currency,
				"line_total_amount": base,
			}
		)
	return lines


def get_payment_tax_invoices(doc):
	"""Sales Tax Invoices of the payment, i.e., undue VAT that becomes due on payment"""
	return frappe.get_all(
		"Sales Tax Invoice",
		filters={"voucher_type": doc.doctype, "voucher_no": doc.name, "docstatus": 1},
		fields=["name", "tax_base", "tax_amount", "tax_percent"],
		order_by="name",
	)


def get_payment_line_items(doc):
	"""Sales Tax Invoices of the payment (undue VAT), else the amount paid per invoice

	Without a Sales Tax Invoice, VAT was due on the invoice, so the receipt
	only acknowledges the amount allocated to each invoice, VAT included.
	"""
	tax_invoices = get_payment_tax_invoices(doc)
	if tax_invoices:
		lines = []
		for inv in tax_invoices:
			# The base of a partial payment is kept unrounded
			base, tax = flt(inv.tax_base, 2), flt(inv.tax_amount, 2)
			lines.append(
				{
					"product_code": inv.name,
					"product_name": inv.name,
					"product_price": base,
					"product_quantity": 1,
					"line_tax_type_code": "VAT" if tax else "FRE",
					"line_tax_rate": flt(inv.tax_percent),
					"line_base_amount": base,
					"line_tax_amount": tax,
					"line_total_amount": flt(base + tax, 2),
				}
			)
		return lines
	paid = defaultdict(float)
	for ref in doc.references:
		if ref.reference_doctype == "Sales Invoice" and flt(ref.allocated_amount):
			paid[ref.reference_name] += flt(ref.allocated_amount)
	# The same text whoever signs, in the language of the system
	lang = frappe.db.get_default("lang")
	lines = []
	for invoice, amount in sorted(paid.items()):
		amount = flt(amount, 2)
		# A credit note set off in the payment is an allowance, as a deposit deduction
		is_allowance = amount < 0
		lines.append(
			{
				"product_code": invoice,
				"product_name": _("Payment for {0}", lang=lang).format(invoice),
				"product_price": 0.0 if is_allowance else amount,
				"product_quantity": 1,
				"line_tax_type_code": "FRE",
				"line_tax_rate": 0.0,
				"line_base_amount": amount,
				"line_tax_amount": 0.0,
				"line_allowance_charge_ind": "false" if is_allowance else "",
				"line_allowance_actual_amount": abs(amount) if is_allowance else 0.0,
				"line_allowance_actual_currency_code": get_currency(doc),
				"line_total_amount": amount,
			}
		)
	return lines


def get_pdf_content(doc, etax_doctype):
	if etax_doctype.template_source != "ERPNext" or not etax_doctype.print_format:
		return ""
	pdf = frappe.get_print(
		doc.doctype, doc.name, etax_doctype.print_format, doc=doc, as_pdf=True
	)
	return base64.b64encode(pdf).decode()


def prepare_payload(doc, etax_doctype):
	if etax_doctype.template_source == "eTax Server":
		form_type, form_name = FORM_TYPE_ETAX_SERVER, etax_doctype.server_print_format
	else:
		form_type, form_name = FORM_TYPE_ERPNEXT, etax_doctype.print_format or ""
	return {
		"doc_data": json.dumps(get_document_data(doc), default=str),
		"form_type": form_type,
		"form_name": form_name,
		"pdf_content": get_pdf_content(doc, etax_doctype),
	}


# ---------------------------------------------------------------------------
# Signing and status update
# ---------------------------------------------------------------------------


def get_error_message(response):
	"""Extract a readable error from a Frappe error response"""
	try:
		data = response.json()
	except ValueError:
		return response.text or str(response.status_code)
	messages = []
	for message in json.loads(data.get("_server_messages") or "[]"):
		try:
			messages.append(json.loads(message).get("message", message))
		except (ValueError, AttributeError):
			messages.append(message)
	return "\n".join(messages) or data.get("exception") or str(response.status_code)


def to_json(value):
	return json.dumps(value, indent=1, default=str)


def log_etax_request(doc, description, url, data, response=None, error=None):
	"""Keep each e-Tax request and its response in Integration Request (API logs)

	error: the exception of a failed request, i.e., timeout or invalid response
	"""
	data = dict(data)
	if data.get("doc_data"):
		data["doc_data"] = json.loads(data["doc_data"])
	if data.get("pdf_content"):
		# The base64 PDF is large, the signed PDF is attached to the document
		data["pdf_content"] = f"<{len(data['pdf_content'])} characters of base64 PDF>"
	output = None
	if response is not None:
		try:
			output = response.json()
		except ValueError:
			output = response.text
	failed = error is not None or not response.ok
	frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": INTEGRATION_SERVICE,
			"request_description": description,
			"status": "Failed" if failed else "Completed",
			"url": url,
			# Request headers are not kept, they hold the API secret
			"data": to_json(data),
			"output": None if failed else to_json(output),
			# The server response tells more than the exception, if any
			"error": to_json(str(error) if output is None else output) if failed else None,
			"reference_doctype": doc.doctype,
			"reference_docname": doc.name,
		}
	).insert(ignore_permissions=True)


def import_etax_master_data():
	"""Create the missing Document Type Codes and Purpose Codes

	Unlike fixtures, the records the user has changed are kept on migrate.
	"""
	for fname in ("etax_document_type_code.json", "etax_purpose_code.json"):
		path = frappe.get_app_path("erpnext_thailand", "thai_etax", "data", fname)
		# A fixed file of this app, not a path from the user
		with open(path, encoding="utf-8") as f:  # nosemgrep
			records = json.load(f)
		for record in records:
			if not frappe.db.exists(record["doctype"], record["name"]):
				frappe.get_doc(record).insert(ignore_permissions=True)


def add_etax_log_permissions():
	"""Let accounts users read the e-Tax request logs from the document connections"""
	from frappe.permissions import add_permission

	for role in ETAX_LOG_ROLES:
		if not frappe.db.exists(
			"Custom DocPerm",
			{"parent": "Integration Request", "role": role, "permlevel": 0, "if_owner": 0},
		):
			add_permission("Integration Request", role)


def add_etax_log_index():
	"""The e-Tax connections of each Sales Invoice / Payment Entry count its
	Integration Requests by reference_docname, which has no index"""
	frappe.db.add_index("Integration Request", ["reference_docname"])


def has_etax_log_access_only(user):
	"""The user reads Integration Requests only through the e-Tax log roles"""
	from frappe.permissions import get_doctype_roles

	other_roles = set(get_doctype_roles("Integration Request")) - set(ETAX_LOG_ROLES)
	return not (set(frappe.get_roles(user)) & other_roles)


def get_etax_log_conditions(user=None):
	"""Integration Request list: accounts users only see the e-Tax logs"""
	user = user or frappe.session.user
	if not has_etax_log_access_only(user):
		return ""
	return "`tabIntegration Request`.integration_request_service = {}".format(
		frappe.db.escape(INTEGRATION_SERVICE)
	)


def has_etax_log_permission(doc, ptype=None, user=None):
	"""Integration Request: accounts users only read the e-Tax logs"""
	user = user or frappe.session.user
	if (
		doc.integration_request_service == INTEGRATION_SERVICE
		or not has_etax_log_access_only(user)
	):
		return None  # role permissions decide
	return False


def lock_before_sign(doc):
	"""Lock the document until the request is committed, so that it is sent once

	A second request for the same document waits for the lock, then gets the
	committed status of the locking read (a plain read may return the snapshot
	taken when its request started, i.e., repeatable read) and stops.
	"""
	status = frappe.db.get_value(doc.doctype, doc.name, "etax_status", for_update=True)
	if status in SIGNED_STATUSES:
		frappe.throw(_("{0}: e-Tax status is already {1}").format(doc.name, status))


@frappe.whitelist(methods=["POST"])
def sign_etax(doctype: str, name: str, etax_document_type: str):
	"""Send a submitted Sales Invoice or Payment Entry to the e-Tax server"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("submit")
	etax_doctype = frappe.get_doc("eTax Document Type", etax_document_type)
	validate_before_sign(doc, etax_doctype)
	doc.etax_document_type = etax_doctype.name
	doc.etax_document_type_code = etax_doctype.document_type_code
	connection = get_etax_connection(doc.company)
	# Errors here are local (i.e., print format) and nothing is sent yet.
	# Rendering the PDF commits (access log), so it is done before the lock.
	payload = prepare_payload(doc, etax_doctype)
	lock_before_sign(doc)
	doc.db_set(
		{
			"etax_document_type": etax_doctype.name,
			"etax_document_type_code": etax_doctype.document_type_code,
		}
	)
	url = connection.server_url + SIGN_ROUTE
	response = None
	try:
		response = requests.post(
			url,
			headers=get_auth_header(connection),
			data=payload,
			timeout=TIMEOUT,
		)
		if not response.ok:
			raise frappe.ValidationError(get_error_message(response))
		message = response.json().get("message") or {}
	except Exception as e:
		log_etax_request(doc, "Sign e-Tax", url, payload, response, e)
		frappe.log_error(f"e-Tax signing failed: {doctype} {name}")
		doc.db_set(
			{"etax_status": "Error", "etax_error_code": "", "etax_error_message": str(e)}
		)
		add_etax_comment(doc)
		return doc.etax_status
	log_etax_request(doc, "Sign e-Tax", url, payload, response)
	update_etax_result(doc, message)
	return doc.etax_status


@frappe.whitelist(methods=["POST"])
def sign_etax_documents(doctype: str, names: str | list, etax_document_type: str):
	"""Sign several documents, i.e., from the list view

	Missing e-Tax emails are reported together before anything is sent.
	"""
	names = frappe.parse_json(names)
	missing = []
	# The customers of many documents are read at once, not each whole document
	party_field = "customer" if doctype == "Sales Invoice" else "party"
	docs = {
		doc.name: frappe._dict(doc, doctype=doctype)
		for doc in frappe.get_all(
			doctype, filters={"name": ("in", names)}, fields=["name", "company", party_field]
		)
	}
	for name in names:
		doc = docs.get(name)
		if not doc:
			continue  # signing reports it, i.e., not permitted
		# Check without throwing, a caught frappe.throw still shows its message
		if is_etax_email_missing(doc, get_etax_connection(doc.company)):
			missing.append(f"{name}: {get_customer(doc)}")
	if missing:
		frappe.throw(
			_("Cannot sign e-Tax. Please fill in e-Tax Email for:")
			+ "<br>"
			+ "<br>".join(missing)
		)
	if len(names) <= SIGN_NOW_LIMIT:
		return sign_documents(doctype, names, etax_document_type)
	frappe.enqueue(
		sign_documents_in_background,
		queue="long",
		timeout=len(names) * 2 * TIMEOUT,
		doctype=doctype,
		names=names,
		etax_document_type=etax_document_type,
	)
	frappe.msgprint(
		_("Signing {0} documents in background, you will be notified of the result.").format(
			len(names)
		),
		alert=True,
	)


def sign_documents_in_background(doctype, names, etax_document_type):
	"""Sign the documents, then notify the user of the result"""
	result = sign_documents(doctype, names, etax_document_type)
	signed = sum(status in SIGNED_STATUSES for status in result.values())
	rows = "".join(
		"<tr><td>{}</td><td>{}</td></tr>".format(
			frappe.utils.escape_html(name), frappe.utils.escape_html(status or "")
		)
		for name, status in result.items()
	)
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"for_user": frappe.session.user,
			"type": "Alert",
			"document_type": doctype,
			"subject": _("e-Tax: {0} of {1} {2} signed").format(signed, len(result), _(doctype)),
			"email_content": f'<table class="table table-bordered">{rows}</table>',
		}
	).insert(ignore_permissions=True)
	frappe.publish_realtime(
		"etax_sign_result",
		{"doctype": doctype, "result": result},
		user=frappe.session.user,
		after_commit=True,
	)


def sign_documents(doctype, names, etax_document_type):
	result = {}
	for name in names:
		frappe.db.savepoint("etax_sign")
		try:
			result[name] = sign_etax(doctype, name, etax_document_type)
		except Exception as e:
			rollback_document(name)
			# i.e., PDF rendering failed, the other documents are still signed
			if not isinstance(e, (frappe.ValidationError, frappe.PermissionError)):
				frappe.log_error(f"e-Tax signing failed: {doctype} {name}")
			result[name] = str(e)
			continue
		if not frappe.flags.in_test:
			# Keep what the server has signed if the request fails later
			frappe.db.commit()  # nosemgrep
	frappe.clear_messages()
	return result


def rollback_document(name):
	"""Undo the changes of a document that failed in a list of documents

	Rendering the PDF commits (access log), which releases the savepoint, then
	the changes since that commit are rolled back.
	"""
	try:
		frappe.db.rollback(save_point="etax_sign")
	except Exception:
		frappe.db.rollback()


def add_etax_comment(doc):
	"""Keep the history of e-Tax results in the document timeline"""
	text = _("e-Tax: {0}").format(doc.etax_status)
	if doc.etax_transaction_code:
		text += f" ({doc.etax_transaction_code})"
	if doc.etax_error_message:
		text += f"<br>{frappe.utils.escape_html(doc.etax_error_code or '')}"
		text += f" {frappe.utils.escape_html(doc.etax_error_message)}"
	doc.add_comment("Info", text)


def get_etax_status(result):
	status = result.get("status")
	return status if status in ETAX_STATUSES else "Processing"


def update_etax_result(doc, result):
	"""Apply an INET ETax Document (status, codes, signed files) to the document"""
	status = get_etax_status(result)
	doc.db_set(
		{
			"etax_status": status,
			"etax_transaction_code": result.get("transaction_code"),
			"etax_error_code": result.get("error_code"),
			"etax_error_message": result.get("error_message"),
		}
	)
	add_etax_comment(doc)
	if status != "Success":
		return
	for ext in ("pdf", "xml"):
		url = result.get(f"{ext}_url")
		if not url:
			continue
		# The document is already signed, a failed download must not undo the status
		try:
			attach_signed_file(doc, url, ext)
		except Exception:
			frappe.log_error(f"e-Tax signed {ext} download failed: {doc.doctype} {doc.name}")
	if (
		doc.amended_from
		and frappe.db.get_value(doc.doctype, doc.amended_from, "etax_status") == "Success"
	):
		frappe.db.set_value(doc.doctype, doc.amended_from, "etax_status", "Replaced")


def attach_signed_file(doc, url, ext):
	response = requests.get(url, timeout=TIMEOUT)
	response.raise_for_status()
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{doc.name}_signed.{ext}",
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"content": response.content,
			"is_private": 1,
		}
	).insert(ignore_permissions=True)


def update_processing_document(doc):
	"""Fetch and apply the latest status of one processing document"""
	if doc.etax_status != "Processing" or not doc.etax_transaction_code:
		return False
	connection = get_etax_connection(doc.company)
	url = connection.server_url + STATUS_ROUTE
	params = {
		"filters": json.dumps([["transaction_code", "=", doc.etax_transaction_code]]),
		"fields": json.dumps(STATUS_FIELDS),
		"limit_page_length": 1,
	}
	try:
		response = requests.get(
			url, headers=get_auth_header(connection), params=params, timeout=TIMEOUT
		)
	except requests.RequestException as e:
		log_etax_request(doc, "Refresh e-Tax Status", url, params, error=e)
		raise
	try:
		documents = response.ok and response.json().get("data") or []
	except ValueError:
		documents = []
	# The scheduler checks every minute, a document still processing keeps no log or comment
	if documents and get_etax_status(documents[0]) == "Processing":
		return False
	log_etax_request(doc, "Refresh e-Tax Status", url, params, response)
	response.raise_for_status()
	if not documents:
		return False
	update_etax_result(doc, documents[0])
	return True


@frappe.whitelist(methods=["POST"])
def refresh_etax_status(doctype: str, name: str):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	update_processing_document(doc)
	return doc.etax_status


def update_processing_documents(limit=100):
	"""Scheduler: update the status of processing e-Tax documents"""
	for doctype in ETAX_DOCTYPES:
		if not frappe.get_meta(doctype).has_field("etax_status"):
			continue
		names = frappe.get_all(
			doctype,
			filters={"etax_status": "Processing"},
			pluck="name",
			order_by="modified",
			limit=limit,
		)
		for name in names:
			frappe.db.savepoint("etax_update")
			try:
				update_processing_document(frappe.get_doc(doctype, name))
			except Exception:
				frappe.db.rollback(save_point="etax_update")
				frappe.log_error(f"e-Tax status update failed: {doctype} {name}")
			if not frappe.flags.in_test:
				# Keep each update, and the error log of a failed one
				frappe.db.commit()  # nosemgrep


# ---------------------------------------------------------------------------
# Replacement
# ---------------------------------------------------------------------------


def check_replacement_lock_day(doc):
	"""A replacement is allowed until the lock day of the month after the document date"""
	lock_day = get_etax_connection(doc.company).replacement_lock_day
	if not lock_day:
		return
	next_month = getdate(add_months(getdate(doc.posting_date).replace(day=1), 1))
	last_day = calendar.monthrange(next_month.year, next_month.month)[1]
	lock_date = next_month.replace(day=min(lock_day, last_day))
	if getdate(today()) > lock_date:
		frappe.throw(
			_("Create Replacement e-Tax not allowed after {0}").format(
				frappe.format(lock_date, "Date")
			)
		)


@frappe.whitelist(methods=["POST"])
def create_replacement(
	doctype: str, name: str, etax_purpose_code: str, etax_purpose: str
):
	"""Cancel a signed document and create its amendment to be signed as replacement"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("cancel")
	if not (doc.docstatus == 1 and doc.etax_status == "Success"):
		frappe.throw(_("Only a successfully signed e-Tax document can be replaced"))
	if doc.etax_document_type_code in NON_TAX_INVOICE_CODES:
		frappe.throw(
			_("Document type code {0} cannot be replaced").format(doc.etax_document_type_code)
		)
	# A replaced note would count as a second adjustment of the same invoice
	if doc.etax_document_type_code in (CREDIT_NOTE_CODE, DEBIT_NOTE_CODE):
		frappe.throw(
			_(
				"A credit or debit note cannot be replaced. Issue another credit or debit note"
				" against {0} to correct it."
			).format(doc.return_against)
		)
	if doc.etax_document_type_code not in get_purpose_codes(etax_purpose_code):
		frappe.throw(
			_("e-Tax Purpose Code {0} cannot be used with document type code {1}.").format(
				etax_purpose_code, doc.etax_document_type_code
			)
		)
	check_replacement_lock_day(doc)

	doc.flags.etax_replacement = True
	cancel_tax_invoices(doc)
	doc.cancel()

	replacement = frappe.copy_doc(doc)
	replacement.docstatus = 0
	replacement.amended_from = doc.name
	replacement.update(
		{
			**{field: None for field in RESULT_FIELDS},
			"etax_document_type": doc.etax_document_type,
			"etax_document_type_code": doc.etax_document_type_code,
			"etax_purpose_code": etax_purpose_code,
			"etax_purpose": etax_purpose,
		}
	)
	replacement.insert()
	remove_signed_files(replacement, doc.name)
	return replacement.name


def cancel_tax_invoices(doc):
	"""Sales Tax Invoices of the document, i.e., undue VAT of a receipt, block its cancellation.
	Submitting the replacement creates them again."""
	names = frappe.get_all(
		"Sales Tax Invoice",
		filters={"voucher_type": doc.doctype, "voucher_no": doc.name, "docstatus": 1},
		pluck="name",
	)
	for name in names:
		tax_invoice = frappe.get_doc("Sales Tax Invoice", name)
		# Cancelled as part of the document the user may cancel
		tax_invoice.flags.ignore_permissions = True
		tax_invoice.cancel()


def remove_signed_files(doc, original):
	"""Frappe copies the attachments of the amended document,
	the signed files of the original are not those of its replacement"""
	files = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"file_name": ("like", f"{original}_signed%"),
		},
		pluck="name",
	)
	for name in files:
		# The file on disk is kept, it is still attached to the original
		frappe.delete_doc("File", name, ignore_permissions=True)
