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
# form_type of etax_inet: "frappe" lets the e-Tax server render its own
# print format, other values mean the source system sends the rendered PDF.
# TODO: send "erpnext" once etax_inet with that form type is deployed
FORM_TYPE_ETAX_SERVER = "frappe"
FORM_TYPE_ERPNEXT = "odoo"
TIMEOUT = 60


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
def is_etax_enabled(company):
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
	"""Return the document this one adjusts (credit/debit note) or replaces (amendment)"""
	if doc.doctype == "Sales Invoice" and doc.return_against:
		return frappe.get_doc("Sales Invoice", doc.return_against)
	if doc.amended_from:
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
		if not doc.amended_from:
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
		doc.etax_purpose = frappe.db.get_value("eTax Purpose Code", doc.etax_purpose_code, "reason")


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
	if not frappe.db.get_value("Company", doc.company, "tax_id"):
		frappe.throw(_("Company {0} does not have a Tax ID configured.").format(doc.company))
	customer = get_customer(doc)
	if not (frappe.db.get_value("Customer", customer, "tax_id") or "").strip():
		frappe.throw(
			_("Cannot sign e-Tax. Please fill in Tax ID for customer {0}.").format(customer)
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
	if (adjustment_code or replacement) and not has_purpose(doc):
		frappe.throw(
			_(
				"{0}: To send this credit note, debit note or replacement as e-Tax,"
				" select an e-Tax Purpose Code and enter its purpose in the e-Tax tab."
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

	if doc.doctype == "Payment Entry" and not get_payment_line_items(doc):
		frappe.throw(
			_(
				"{0}: no e-Tax line items found. Add Sales Tax Invoice information"
				" or allocate the payment to a Sales Invoice before signing e-Tax."
			).format(doc.name)
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
	return (
		doc.currency if doc.doctype == "Sales Invoice" else doc.paid_from_account_currency
	)


def get_customer_address(doc):
	from frappe.contacts.doctype.address.address import get_default_address

	name = doc.get("customer_address") or get_default_address(
		"Customer", get_customer(doc)
	)
	return name and frappe.get_doc("Address", name) or frappe._dict()


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
		"seller_branch_id": company_address.get("branch_code") or "00000",
		"source_system": get_url(),
		"send_mail": get_etax_connection(doc.company).send_email and "Y" or "N",
		"seller_tax_id": frappe.db.get_value("Company", doc.company, "tax_id"),
		"buyer_name": customer.customer_name,
		"buyer_type": "TXID",
		"buyer_tax_id": customer.tax_id,
		"buyer_branch_id": customer.get("branch_code") or "00000",
		"buyer_email": customer.get("email_etax"),
		"buyer_zip": address.get("pincode") or "",
		"buyer_building_name": "",
		"buyer_building_no": "",
		"buyer_address_line1": address.get("address_line1") or "",
		"buyer_address_line2": address.get("address_line2") or "",
		"buyer_address_line3": " ".join(
			filter(None, [address.get("city"), address.get("state")])
		),
		"buyer_address_line4": address.get("pincode") or "",
		"buyer_address_line5": "",
		"buyer_city_name": address.get("city") or "",
		"buyer_country_code": country_code.upper(),
	}
	if doc.doctype == "Sales Invoice":
		lines = get_invoice_line_items(doc)
		original, adjustment, corrected = get_additional_amount(doc)
		data.update(
			{
				"buyer_ref_document": doc.po_no or "",
				"original_amount_untaxed": original,
				# Credit/debit notes send the corrected amount, else the line total
				"final_amount_untaxed": corrected
				if doc.return_against
				else flt(sum(line["line_base_amount"] for line in lines), 2),
				"adjust_amount_untaxed": adjustment,
				"line_item_information": lines,
			}
		)
	else:
		data.update(
			{
				"buyer_ref_document": "",
				"original_amount_untaxed": False,
				"final_amount_untaxed": False,
				"adjust_amount_untaxed": False,
				"line_item_information": get_payment_line_items(doc),
			}
		)
	return data


def get_additional_amount(doc):
	"""Untaxed amounts of a credit/debit note

	f36_original_total_amount = original
	f40_adjusted_information_amount = adjustment
	f38_line_total_amount = corrected
	"""
	if not doc.return_against:
		return (False, False, flt(doc.net_total))
	original = flt(frappe.db.get_value("Sales Invoice", doc.return_against, "net_total"))
	adjustment = abs(flt(doc.net_total))
	if doc.is_return:
		return (original, adjustment, original - adjustment)
	return (original, adjustment, original + adjustment)


def get_item_taxes(doc):
	"""Return {item key: [rate, tax amount]} of all 'On Net Total' taxes (VAT)"""
	taxes = {}
	for tax in doc.taxes:
		if tax.charge_type != "On Net Total":
			continue
		detail = tax.item_wise_tax_detail
		detail = json.loads(detail) if isinstance(detail, str) else (detail or {})
		for key, (rate, amount) in detail.items():
			item_tax = taxes.setdefault(key, [0.0, 0.0])
			item_tax[0] += flt(rate)
			item_tax[1] += flt(amount)
	return taxes


def get_etax_items(doc):
	"""Priced lines and deductions, i.e., a fully discounted line is still sent"""
	return [
		item
		for item in doc.items
		if not item.get("skip_etax")
		and (get_undiscounted_rate(item) > 0 or flt(item.net_amount) < 0)
	]


def get_undiscounted_rate(item):
	"""Rate before discount, i.e., a rate above the price list has no discount"""
	return max(abs(flt(item.price_list_rate)), abs(flt(item.rate)))


def get_price_tax_factor(doc):
	"""Divisor that removes VAT from item prices when taxes are included in the rate"""
	rate = sum(
		flt(tax.rate)
		for tax in doc.taxes
		if tax.charge_type == "On Net Total" and tax.included_in_print_rate
	)
	return 1 + rate / 100


def get_invoice_line_amounts(doc):
	"""Return {row name: (rate, base, tax, has_tax)}, signed positive for credit notes

	ERPNext keeps item taxes per item code, so the tax of an item code is
	split between its rows by net amount, the last row taking the rounding.
	"""
	sign = -1 if doc.is_return else 1
	item_taxes = get_item_taxes(doc)
	groups = defaultdict(list)
	for item in doc.items:
		groups[item.item_code or item.item_name].append(item)
	amounts = {}
	for key, items in groups.items():
		rate, tax_total = item_taxes.get(key, (0.0, 0.0))
		group_net = sum(flt(item.net_amount) for item in items)
		remaining = flt(tax_total, 2)
		for i, item in enumerate(items):
			if i == len(items) - 1:
				tax = remaining
			else:
				tax = flt(tax_total * flt(item.net_amount) / group_net, 2) if group_net else 0.0
				remaining = flt(remaining - tax, 2)
			amounts[item.name] = (
				rate,
				flt(sign * item.net_amount, 2),
				flt(sign * tax, 2),
				key in item_taxes,
			)
	return amounts


def get_invoice_line_items(doc):
	"""Lines keep their signed base, tax and total, the receiver sums them as is

	A discount (item or document level) is sent as the line allowance (L27)
	between the undiscounted price before VAT and the line base.
	"""
	line_amounts = get_invoice_line_amounts(doc)
	price_factor = get_price_tax_factor(doc)
	lines = []
	for item in get_etax_items(doc):
		rate, base, tax, has_tax = line_amounts[item.name]
		qty = abs(flt(item.qty))
		price = get_undiscounted_rate(item) / price_factor
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
	return lines


def get_payment_line_items(doc):
	"""Sales Tax Invoices of the payment (undue VAT), else the paid invoices' items as exempt"""
	tax_invoices = frappe.get_all(
		"Sales Tax Invoice",
		filters={"voucher_type": doc.doctype, "voucher_no": doc.name, "docstatus": 1},
		fields=["name", "tax_base", "tax_amount", "tax_percent"],
		order_by="name",
	)
	if tax_invoices:
		return [
			{
				"product_code": inv.name,
				"product_name": inv.name,
				"product_price": flt(inv.tax_base),
				"product_quantity": 1,
				"line_tax_type_code": "VAT" if inv.tax_amount else "FRE",
				"line_tax_rate": flt(inv.tax_percent),
				"line_base_amount": flt(inv.tax_base),
				"line_tax_amount": flt(inv.tax_amount),
				"line_total_amount": flt(inv.tax_base) + flt(inv.tax_amount),
			}
			for inv in tax_invoices
		]
	lines = []
	invoices = {
		ref.reference_name
		for ref in doc.references
		if ref.reference_doctype == "Sales Invoice"
	}
	for invoice in sorted(invoices):
		for item in frappe.get_doc("Sales Invoice", invoice).items:
			lines.append(
				{
					"product_code": "",
					"product_name": item.item_name or item.item_code,
					"product_price": flt(item.net_rate),
					"product_quantity": flt(item.qty),
					"line_tax_type_code": "FRE",
					"line_tax_rate": 0.0,
					"line_base_amount": flt(item.net_amount),
					"line_tax_amount": 0.0,
					"line_total_amount": flt(item.net_amount),
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


@frappe.whitelist()
def sign_etax(doctype, name, etax_document_type):
	"""Send a submitted Sales Invoice or Payment Entry to the e-Tax server"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("submit")
	etax_doctype = frappe.get_doc("eTax Document Type", etax_document_type)
	validate_before_sign(doc, etax_doctype)
	doc.db_set(
		{
			"etax_document_type": etax_doctype.name,
			"etax_document_type_code": etax_doctype.document_type_code,
		}
	)
	connection = get_etax_connection(doc.company)
	# Errors here are local (i.e., print format) and nothing is sent yet
	payload = prepare_payload(doc, etax_doctype)
	try:
		response = requests.post(
			connection.server_url + SIGN_ROUTE,
			headers=get_auth_header(connection),
			data=payload,
			timeout=TIMEOUT,
		)
		if not response.ok:
			raise frappe.ValidationError(get_error_message(response))
		message = response.json().get("message") or {}
	except Exception as e:
		frappe.log_error(f"e-Tax signing failed: {doctype} {name}")
		doc.db_set(
			{"etax_status": "Error", "etax_error_code": "", "etax_error_message": str(e)}
		)
		add_etax_comment(doc)
		return doc.etax_status
	update_etax_result(doc, message)
	return doc.etax_status


@frappe.whitelist()
def sign_etax_documents(doctype, names, etax_document_type):
	"""Sign several documents, i.e., from the list view

	Missing e-Tax emails are reported together before anything is sent.
	"""
	names = frappe.parse_json(names)
	missing = []
	for name in names:
		doc = frappe.get_doc(doctype, name)
		# Check without throwing, a caught frappe.throw still shows its message
		if is_etax_email_missing(doc, get_etax_connection(doc.company)):
			missing.append(f"{name}: {get_customer(doc)}")
	if missing:
		frappe.throw(
			_("Cannot sign e-Tax. Please fill in e-Tax Email for:")
			+ "<br>"
			+ "<br>".join(missing)
		)
	result = {}
	for name in names:
		frappe.db.savepoint("etax_sign")
		try:
			result[name] = sign_etax(doctype, name, etax_document_type)
		except frappe.ValidationError as e:
			frappe.db.rollback(save_point="etax_sign")
			result[name] = str(e)
			continue
		if not frappe.flags.in_test:
			frappe.db.commit()  # keep what the server has signed if the request fails later
	frappe.clear_messages()
	return result


def add_etax_comment(doc):
	"""Keep the history of e-Tax results in the document timeline"""
	text = _("e-Tax: {0}").format(doc.etax_status)
	if doc.etax_transaction_code:
		text += f" ({doc.etax_transaction_code})"
	if doc.etax_error_message:
		text += f"<br>{frappe.utils.escape_html(doc.etax_error_code or '')}"
		text += f" {frappe.utils.escape_html(doc.etax_error_message)}"
	doc.add_comment("Info", text)


def update_etax_result(doc, result):
	"""Apply an INET ETax Document (status, codes, signed files) to the document"""
	status = result.get("status")
	status = status if status in ETAX_STATUSES else "Processing"
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
	response = requests.get(
		connection.server_url + STATUS_ROUTE,
		headers=get_auth_header(connection),
		params={
			"filters": json.dumps([["transaction_code", "=", doc.etax_transaction_code]]),
			"fields": json.dumps(STATUS_FIELDS),
			"limit_page_length": 1,
		},
		timeout=TIMEOUT,
	)
	response.raise_for_status()
	documents = response.json().get("data") or []
	if not documents:
		return False
	update_etax_result(doc, documents[0])
	return True


@frappe.whitelist()
def refresh_etax_status(doctype, name):
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
			try:
				update_processing_document(frappe.get_doc(doctype, name))
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				frappe.log_error(f"e-Tax status update failed: {doctype} {name}")


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


@frappe.whitelist()
def create_replacement(doctype, name, etax_purpose_code, etax_purpose):
	"""Cancel a signed document and create its amendment to be signed as replacement"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("cancel")
	if not (doc.docstatus == 1 and doc.etax_status == "Success"):
		frappe.throw(_("Only a successfully signed e-Tax document can be replaced"))
	if doc.etax_document_type_code in NON_TAX_INVOICE_CODES:
		frappe.throw(
			_("Document type code {0} cannot be replaced").format(doc.etax_document_type_code)
		)
	if doc.etax_document_type_code not in get_purpose_codes(etax_purpose_code):
		frappe.throw(
			_("e-Tax Purpose Code {0} cannot be used with document type code {1}.").format(
				etax_purpose_code, doc.etax_document_type_code
			)
		)
	check_replacement_lock_day(doc)

	doc.flags.etax_replacement = True
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
	return replacement.name
