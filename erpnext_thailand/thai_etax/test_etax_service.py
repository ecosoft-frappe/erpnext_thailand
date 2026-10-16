# Copyright (c) 2026, Ecosoft and contributors
# For license information, please see license.txt

import base64
import json
from io import BytesIO
from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, flt, getdate, today
from pypdf import PdfWriter

from erpnext_thailand.thai_etax import etax_service

SERVER = "https://etax.test"


def pdf_content():
	writer = PdfWriter()
	writer.add_blank_page(10, 10)
	content = BytesIO()
	writer.write(content)
	return content.getvalue()


class FakeResponse:
	def __init__(self, data=None, content=b"", status_code=200):
		self.data = data
		self.content = content
		self.status_code = status_code
		self.ok = status_code < 400
		self.text = ""

	def json(self):
		return self.data

	def raise_for_status(self):
		if not self.ok:
			raise Exception(self.status_code)


class FakeServer:
	"""Stand-in for the Frappe e-Tax server (etax_inet)"""

	def __init__(self):
		self.status = "Success"
		self.requests = []
		self.post_response = None

	def post(self, url, headers=None, data=None, timeout=None):
		self.requests.append({"url": url, "headers": headers, "data": data})
		if self.post_response:
			return self.post_response
		return FakeResponse(
			{
				"message": {
					"status": self.status,
					"transaction_code": f"TX{len(self.requests)}",
					"error_code": "ER01" if self.status == "Error" else None,
					"error_message": "Invalid data" if self.status == "Error" else None,
					"pdf_url": f"{SERVER}/signed.pdf",
					"xml_url": f"{SERVER}/signed.xml",
				}
			}
		)

	def get(self, url, headers=None, params=None, timeout=None):
		if params:  # status of processing documents
			code = json.loads(params["filters"])[0][2]
			return FakeResponse(
				{
					"data": [
						{"status": "Success", "transaction_code": code, "pdf_url": f"{SERVER}/signed.pdf"}
					]
				}
			)
		return FakeResponse(content=pdf_content() if url.endswith(".pdf") else b"<xml/>")

	@property
	def doc_data(self):
		return json.loads(self.requests[-1]["data"]["doc_data"])


class TestETaxService(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all(
			"Company", filters={"default_currency": ("is", "set")}, pluck="name"
		)[0]
		frappe.db.set_value("Company", cls.company, "tax_id", "0105551234567")
		settings = frappe.get_single("Thai Tax Settings")
		if cls.company not in [row.company for row in settings.company_accounts]:
			settings.append("company_accounts", {"company": cls.company})
			settings.flags.ignore_links = True
			settings.save(ignore_permissions=True)
		cls.vat_account = cls.make_vat_account()
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "eTax Seller",
				"address_line1": "1 Road",
				"city": "Bangkok",
				"country": "Thailand",
				"is_your_company_address": 1,
				"branch_code": "00001",
				"links": [{"link_doctype": "Company", "link_name": cls.company}],
			}
		).insert()
		cls.customer = (
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": "_Test eTax Customer",
					"tax_id": "0105559999999",
					"branch_code": "00002",
					"email_etax": "billing@example.com,accounting@example.com",
				}
			)
			.insert()
			.name
		)
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "eTax Buyer",
				"address_line1": "99 Silom Road",
				"address_line2": "Suriyawong",
				"city": "Bang Rak",
				"state": "Bangkok",
				"pincode": "10500",
				"country": "Thailand",
				"is_primary_address": 1,
				"links": [{"link_doctype": "Customer", "link_name": cls.customer}],
			}
		).insert()
		for item_code in ("_Test eTax A", "_Test eTax B"):
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": item_code,
						"item_group": "All Item Groups",
						"is_stock_item": 0,
						"stock_uom": "Nos",
					}
				).insert()
		frappe.get_doc(
			{
				"doctype": "eTax Connection",
				"company": cls.company,
				"server_url": f"{SERVER}/",
				"api_key": "key",
				"api_secret": "secret",
				"send_email": 1,
				"replacement_lock_day": 0,
			}
		).insert()
		for name, applies_to, code in (
			("_Test INV", "Sales Invoice", "T02"),
			("_Test BILL", "Sales Invoice", "380"),
			("_Test CN", "Credit Note", "81"),
			("_Test DN", "Debit Note", "80"),
			("_Test RC", "Payment Entry", "T01"),
		):
			doc = frappe.new_doc("eTax Document Type")
			doc.update(
				{
					"applies_to": applies_to,
					"document_type_code": code,
					"template_source": "eTax Server",
				}
			)
			doc.server_print_format = name
			doc.insert(set_name=name)

	@classmethod
	def make_vat_account(cls):
		parent = frappe.db.get_value(
			"Account", {"company": cls.company, "is_group": 1, "root_type": "Liability"}, "name"
		)
		return (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "_Test eTax VAT",
					"company": cls.company,
					"parent_account": parent,
					"account_type": "Tax",
					"tax_rate": 7,
				}
			)
			.insert()
			.name
		)

	def setUp(self):
		frappe.db.savepoint("etax_test")
		self.addCleanup(frappe.db.rollback, save_point="etax_test")
		self.server = FakeServer()
		patcher = patch.multiple(
			etax_service.requests, post=self.server.post, get=self.server.get
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	# -- helpers

	def set_connection(self, **values):
		connection = frappe.get_doc("eTax Connection", self.company)
		connection.update(values)
		connection.save()

	def make_invoice(self, items=None, included_in_print_rate=0, submit=True, **values):
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": self.customer,
				"posting_date": values.pop("posting_date", today()),
				"set_posting_time": 1,
				"items": items
				or [
					{"item_code": "_Test eTax A", "qty": 2, "rate": 100.33},
					{"item_code": "_Test eTax A", "qty": 1, "rate": 50},
					{"item_code": "_Test eTax B", "qty": 3, "rate": 33.33},
				],
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": self.vat_account,
						"description": "VAT 7%",
						"rate": 7,
						"included_in_print_rate": included_in_print_rate,
					}
				],
				**values,
			}
		)
		invoice.insert()
		if submit:
			invoice.submit()
		return invoice

	def sign(self, doc, etax_document_type="_Test INV"):
		etax_service.sign_etax(doc.doctype, doc.name, etax_document_type)
		doc.reload()
		return doc

	def lines(self, invoice):
		return etax_service.get_invoice_line_items(invoice)

	# -- configuration

	def test_connection_validates_server_url(self):
		connection = frappe.get_doc("eTax Connection", self.company)
		self.assertEqual(connection.server_url, SERVER)
		connection.server_url = "etax.test"
		self.assertRaises(frappe.ValidationError, connection.save)

	def test_custom_fields_and_master_data(self):
		self.assertTrue(frappe.get_meta("Sales Invoice").has_field("etax_status"))
		self.assertTrue(frappe.get_meta("Payment Entry").has_field("etax_status"))
		self.assertTrue(frappe.get_meta("Sales Invoice Item").has_field("skip_etax"))
		self.assertTrue(frappe.get_meta("Customer").has_field("email_etax"))
		self.assertTrue(frappe.db.exists("eTax Document Type Code", "T02"))
		self.assertEqual(etax_service.get_purpose_codes("CDNG01"), ["81"])

	# -- payload

	def test_invoice_payload(self):
		invoice = self.sign(self.make_invoice())
		request = self.server.requests[-1]
		self.assertEqual(request["url"], SERVER + etax_service.SIGN_ROUTE)
		self.assertEqual(request["headers"], {"Authorization": "token key:secret"})
		self.assertEqual(request["data"]["form_type"], "frappe")
		self.assertEqual(request["data"]["form_name"], "_Test INV")
		data = self.server.doc_data
		self.assertEqual(data["document_type_code"], "T02")
		self.assertEqual(data["document_id"], invoice.name)
		self.assertEqual(data["document_issue_dtm"], f"{today()}T00:00:00")
		self.assertEqual(data["seller_tax_id"], "0105551234567")
		self.assertEqual(data["seller_branch_id"], "00001")
		self.assertEqual(data["buyer_tax_id"], "0105559999999")
		self.assertEqual(data["buyer_branch_id"], "00002")
		self.assertEqual(data["buyer_email"], "billing@example.com,accounting@example.com")
		self.assertEqual(data["buyer_address_line3"], "Bang Rak Bangkok")
		self.assertEqual(data["buyer_zip"], "10500")
		self.assertEqual(data["buyer_country_code"], "TH")
		self.assertEqual(data["send_mail"], "Y")
		self.assertEqual(data["final_amount_untaxed"], invoice.net_total)
		self.assertFalse(data["ref_document_id"])
		lines = data["line_item_information"]
		self.assertEqual(len(lines), 3)
		# Tax per item code is split between its rows and sums to the invoice tax
		self.assertEqual(
			flt(sum(line["line_tax_amount"] for line in lines), 2),
			invoice.total_taxes_and_charges,
		)
		self.assertEqual(
			flt(sum(line["line_total_amount"] for line in lines), 2), invoice.grand_total
		)
		self.assertEqual(lines[0]["line_tax_type_code"], "VAT")
		self.assertEqual(lines[0]["line_tax_rate"], 7)

	def test_discount_is_line_allowance(self):
		invoice = self.make_invoice(
			[
				{
					"item_code": "_Test eTax A",
					"qty": 2,
					"price_list_rate": 100,
					"discount_percentage": 10,
				}
			],
			submit=False,
		)
		line = self.lines(invoice)[0]
		self.assertEqual(line["product_price"], 100)
		self.assertEqual(line["product_quantity"], 2)
		self.assertEqual(line["line_base_amount"], 180)
		self.assertEqual(line["line_allowance_charge_ind"], "false")
		self.assertEqual(line["line_allowance_actual_amount"], 20)

	def test_rate_above_price_list_has_no_allowance(self):
		invoice = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": 2, "price_list_rate": 100, "rate": 120}],
			submit=False,
		)
		invoice.items[0].rate = 120
		invoice.save()
		line = self.lines(invoice)[0]
		self.assertEqual(line["product_price"], 120)
		self.assertEqual(line["line_base_amount"], 240)
		self.assertEqual(line["line_allowance_actual_amount"], 0)
		self.assertEqual(line["line_allowance_charge_ind"], "")

	def test_discount_excludes_price_included_vat(self):
		invoice = self.make_invoice(
			[
				{
					"item_code": "_Test eTax A",
					"qty": 2,
					"price_list_rate": 107,
					"discount_percentage": 10,
				}
			],
			included_in_print_rate=1,
			submit=False,
		)
		line = self.lines(invoice)[0]
		self.assertEqual(line["product_price"], 100)
		self.assertEqual(line["line_allowance_actual_amount"], 20)
		self.assertEqual(line["line_base_amount"], 180)
		self.assertEqual(line["line_tax_amount"], 12.6)
		self.assertEqual(line["line_total_amount"], 192.6)

	def test_full_discount_line_is_sent(self):
		invoice = self.make_invoice(
			[
				{"item_code": "_Test eTax A", "qty": 1, "rate": 300},
				{
					"item_code": "_Test eTax B",
					"qty": 2,
					"price_list_rate": 100,
					"discount_percentage": 100,
				},
			],
			submit=False,
		)
		line = self.lines(invoice)[1]
		self.assertEqual(line["line_base_amount"], 0)
		self.assertEqual(line["line_allowance_actual_amount"], 200)
		self.assertEqual(line["product_price"], 100)

	def test_skip_etax_line(self):
		invoice = self.make_invoice(
			[
				{"item_code": "_Test eTax A", "qty": 1, "rate": 300},
				{"item_code": "_Test eTax B", "qty": 1, "rate": 20, "skip_etax": 1},
			],
			submit=False,
		)
		self.assertEqual(
			[line["product_code"] for line in self.lines(invoice)], ["_Test eTax A"]
		)

	def test_negative_line_is_allowance(self):
		invoice = self.make_invoice(
			[
				{"item_code": "_Test eTax A", "qty": 1, "rate": 300},
				{"item_code": "_Test eTax B", "qty": 1, "rate": -120},
			],
			submit=False,
		)
		line = self.lines(invoice)[1]
		self.assertEqual(line["line_base_amount"], -120)
		self.assertEqual(line["line_tax_amount"], -8.4)
		self.assertEqual(line["line_total_amount"], -128.4)
		self.assertEqual(line["product_price"], 0)
		self.assertEqual(line["product_quantity"], 1)
		self.assertEqual(line["line_allowance_charge_ind"], "false")
		self.assertEqual(line["line_allowance_actual_amount"], 120)
		self.assertEqual(etax_service.get_document_data(invoice)["final_amount_untaxed"], 180)

	def test_exempt_line(self):
		invoice = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 120}], submit=False
		)
		invoice.taxes = []
		invoice.save()
		line = self.lines(invoice)[0]
		self.assertEqual(line["line_tax_type_code"], "FRE")
		self.assertEqual(line["line_tax_amount"], 0)
		self.assertEqual(line["line_allowance_actual_amount"], 0)

	# -- signing

	def test_sign_success_attaches_signed_files(self):
		invoice = self.sign(self.make_invoice())
		self.assertEqual(invoice.etax_status, "Success")
		self.assertEqual(invoice.etax_document_type, "_Test INV")
		self.assertEqual(invoice.etax_document_type_code, "T02")
		self.assertEqual(invoice.etax_transaction_code, "TX1")
		files = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Sales Invoice", "attached_to_name": invoice.name},
			pluck="file_name",
		)
		# File may add a suffix when the same name exists on disk
		self.assertEqual(len(files), 2)
		self.assertTrue(all(name.startswith(f"{invoice.name}_signed") for name in files))
		self.assertEqual({name.rsplit(".", 1)[1] for name in files}, {"pdf", "xml"})
		self.assertTrue(
			frappe.db.exists(
				"Comment", {"reference_name": invoice.name, "content": ("like", "e-Tax: Success%")}
			)
		)
		self.assertRaises(frappe.ValidationError, self.sign, invoice)

	def test_sign_error_from_server(self):
		self.server.status = "Error"
		invoice = self.sign(self.make_invoice())
		self.assertEqual(invoice.etax_status, "Error")
		self.assertEqual(invoice.etax_error_code, "ER01")
		self.assertEqual(invoice.etax_error_message, "Invalid data")
		# An error can be signed again
		self.server.status = "Success"
		self.assertEqual(self.sign(invoice).etax_status, "Success")

	def test_sign_http_error(self):
		self.server.post_response = FakeResponse(
			{"_server_messages": json.dumps([json.dumps({"message": "Not permitted"})])},
			status_code=403,
		)
		invoice = self.sign(self.make_invoice())
		self.assertEqual(invoice.etax_status, "Error")
		self.assertIn("Not permitted", invoice.etax_error_message)

	def test_sign_validation(self):
		draft = self.make_invoice(submit=False)
		self.assertRaises(frappe.ValidationError, self.sign, draft)
		invoice = self.make_invoice()
		self.assertRaises(frappe.ValidationError, self.sign, invoice, "_Test CN")
		self.set_connection(enabled=0)
		self.assertRaises(frappe.ValidationError, self.sign, invoice)
		self.assertEqual(self.server.requests, [])

	def test_required_etax_email(self):
		self.set_connection(require_email=1)
		frappe.db.set_value("Customer", self.customer, "email_etax", "")
		invoices = [self.make_invoice(), self.make_invoice()]
		self.assertRaises(frappe.ValidationError, self.sign, invoices[0])
		# Several documents report the missing emails together before sending
		frappe.clear_messages()
		with self.assertRaises(frappe.ValidationError) as error:
			etax_service.sign_etax_documents(
				"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
			)
		for invoice in invoices:
			self.assertIn(invoice.name, str(error.exception))
		# Only the combined message is shown, not one per document as well
		self.assertEqual(len(frappe.local.message_log), 1)
		self.assertEqual(self.server.requests, [])
		# Without the requirement, sign without email delivery
		self.set_connection(require_email=0)
		self.sign(invoices[0])
		self.assertFalse(self.server.doc_data["buyer_email"])

	def test_cancel_signed_document_is_blocked(self):
		invoice = self.sign(self.make_invoice())
		self.assertRaises(frappe.ValidationError, invoice.cancel)

	def test_amendment_resets_etax_result(self):
		self.server.status = "Error"
		invoice = self.sign(self.make_invoice())
		invoice.cancel()
		amended = frappe.copy_doc(invoice)
		amended.docstatus = 0
		amended.amended_from = invoice.name
		amended.etax_status = "Error"
		amended.insert()
		self.assertFalse(amended.etax_status)
		self.assertFalse(amended.etax_error_message)

	# -- credit and debit notes

	def test_credit_note(self):
		invoice = self.sign(self.make_invoice())
		credit_note = make_sales_return(invoice.name)
		credit_note.items = credit_note.items[:1]
		credit_note.items[0].qty = -1
		credit_note.etax_purpose_code = "TIVC01"  # not for credit notes
		self.assertRaises(frappe.ValidationError, credit_note.insert)
		credit_note.etax_purpose_code = None
		credit_note.insert()
		credit_note.submit()
		# Purpose is required before signing, and can be set after submit
		self.assertRaises(frappe.ValidationError, self.sign, credit_note, "_Test CN")
		credit_note.etax_purpose_code = "CDNG02"
		credit_note.etax_purpose = "Damaged goods"
		credit_note.save()
		self.assertRaises(frappe.ValidationError, self.sign, credit_note, "_Test INV")
		self.sign(credit_note, "_Test CN")
		self.assertEqual(credit_note.etax_status, "Success")
		data = self.server.doc_data
		self.assertEqual(data["create_purpose_code"], "CDNG02")
		self.assertEqual(data["create_purpose"], "Damaged goods")
		self.assertEqual(data["ref_document_id"], invoice.name)
		self.assertEqual(data["ref_document_type_code"], "T02")
		self.assertEqual(data["original_amount_untaxed"], invoice.net_total)
		self.assertEqual(data["adjust_amount_untaxed"], 100.33)
		self.assertEqual(data["final_amount_untaxed"], invoice.net_total - 100.33)
		line = data["line_item_information"][0]
		self.assertEqual(line["product_quantity"], 1)
		self.assertEqual(line["line_base_amount"], 100.33)
		self.assertGreater(line["line_tax_amount"], 0)
		# Purpose cannot change once signed
		credit_note.etax_purpose = "Other"
		self.assertRaises(frappe.ValidationError, credit_note.save)

	def test_no_credit_note_for_invoice_code_380(self):
		invoice = self.sign(self.make_invoice(), "_Test BILL")
		credit_note = make_sales_return(invoice.name)
		credit_note.etax_purpose_code = "CDNG05"
		credit_note.insert()
		credit_note.submit()
		self.assertRaises(frappe.ValidationError, self.sign, credit_note, "_Test CN")
		self.assertEqual(len(self.server.requests), 1)

	def test_full_credit_note(self):
		invoice = self.sign(self.make_invoice())
		credit_note = make_sales_return(invoice.name)
		credit_note.etax_purpose_code = "CDNG05"
		credit_note.insert()
		credit_note.submit()
		self.sign(credit_note, "_Test CN")
		data = self.server.doc_data
		self.assertEqual(data["adjust_amount_untaxed"], invoice.net_total)
		self.assertEqual(data["final_amount_untaxed"], 0)
		# The original keeps its own payload after the adjustment
		self.assertEqual(
			etax_service.get_document_data(invoice)["final_amount_untaxed"], invoice.net_total
		)

	def test_debit_note(self):
		invoice = self.sign(self.make_invoice())
		debit_note = self.make_invoice(
			[{"item_code": "_Test eTax B", "qty": 1, "rate": 120}],
			is_debit_note=1,
			return_against=invoice.name,
			etax_purpose_code="DBNG01",
		)
		self.assertTrue(debit_note.etax_purpose)  # the reason of the purpose code
		self.sign(debit_note, "_Test DN")
		data = self.server.doc_data
		self.assertEqual(data["document_type_code"], "80")
		self.assertEqual(data["original_amount_untaxed"], invoice.net_total)
		self.assertEqual(data["adjust_amount_untaxed"], 120)
		self.assertEqual(data["final_amount_untaxed"], invoice.net_total + 120)

	# -- replacement

	def test_replacement(self):
		invoice = self.sign(self.make_invoice())
		self.assertRaises(
			frappe.ValidationError,
			etax_service.create_replacement,
			"Sales Invoice",
			invoice.name,
			"CDNG01",
			"Wrong purpose code",
		)
		name = etax_service.create_replacement(
			"Sales Invoice", invoice.name, "TIVC02", "Wrong address"
		)
		self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.name, "docstatus"), 2)
		replacement = frappe.get_doc("Sales Invoice", name)
		self.assertEqual(replacement.amended_from, invoice.name)
		self.assertEqual(replacement.etax_document_type, "_Test INV")
		self.assertFalse(replacement.etax_status)
		replacement.submit()
		self.assertRaises(frappe.ValidationError, self.sign, replacement, "_Test BILL")
		self.sign(replacement)
		data = self.server.doc_data
		self.assertEqual(data["ref_document_id"], invoice.name)
		self.assertEqual(data["ref_document_type_code"], "T02")
		self.assertEqual(data["create_purpose_code"], "TIVC02")
		self.assertFalse(data["original_amount_untaxed"])
		self.assertFalse(data["adjust_amount_untaxed"])
		self.assertEqual(data["final_amount_untaxed"], replacement.net_total)
		self.assertEqual(
			frappe.db.get_value("Sales Invoice", invoice.name, "etax_status"), "Replaced"
		)

	def test_no_replacement_for_invoice_code_380(self):
		invoice = self.sign(self.make_invoice(), "_Test BILL")
		self.assertRaises(
			frappe.ValidationError,
			etax_service.create_replacement,
			"Sales Invoice",
			invoice.name,
			"TIVC01",
			"Wrong name",
		)

	def test_replacement_lock_day(self):
		self.set_connection(replacement_lock_day=5)
		old = frappe._dict(company=self.company, posting_date=add_months(today(), -2))
		self.assertRaises(
			frappe.ValidationError, etax_service.check_replacement_lock_day, old
		)
		etax_service.check_replacement_lock_day(
			frappe._dict(company=self.company, posting_date=today())
		)
		# The lock day of the next month after the document date
		last_month = getdate(add_months(today(), -1)).replace(day=1)
		lock_date = getdate(add_months(last_month, 1)).replace(day=5)
		doc = frappe._dict(company=self.company, posting_date=last_month)
		if getdate(today()) > lock_date:
			self.assertRaises(
				frappe.ValidationError, etax_service.check_replacement_lock_day, doc
			)
		else:
			etax_service.check_replacement_lock_day(doc)

	# -- receipts

	def make_payment(self, invoice):
		payment = get_payment_entry("Sales Invoice", invoice.name)
		payment.reference_no = "REF"
		payment.reference_date = today()
		payment.insert()
		payment.submit()
		return payment

	def test_receipt_with_invoice_lines(self):
		invoice = self.make_invoice()
		payment = self.make_payment(invoice)
		self.assertRaises(frappe.ValidationError, self.sign, payment, "_Test INV")
		self.sign(payment, "_Test RC")
		self.assertEqual(payment.etax_status, "Success")
		data = self.server.doc_data
		self.assertEqual(data["document_type_code"], "T01")
		self.assertIs(data["original_amount_untaxed"], False)
		self.assertIs(data["adjust_amount_untaxed"], False)
		lines = data["line_item_information"]
		self.assertEqual(len(lines), len(invoice.items))
		self.assertEqual({line["line_tax_type_code"] for line in lines}, {"FRE"})

	def test_receipt_replacement(self):
		payment = self.sign(self.make_payment(self.make_invoice()), "_Test RC")
		name = etax_service.create_replacement(
			"Payment Entry", payment.name, "RCTC01", "Wrong name"
		)
		replacement = frappe.get_doc("Payment Entry", name)
		replacement.submit()
		self.sign(replacement, "_Test RC")
		self.assertEqual(self.server.doc_data["ref_document_id"], payment.name)
		self.assertEqual(
			frappe.db.get_value("Payment Entry", payment.name, "etax_status"), "Replaced"
		)

	def test_receipt_with_undue_tax_invoice(self):
		"""Undue VAT becomes due on payment, the receipt sends its Sales Tax Invoice"""
		undue_account = (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "_Test eTax Undue VAT",
					"company": self.company,
					"parent_account": frappe.db.get_value(
						"Account", self.vat_account, "parent_account"
					),
					"account_type": "Tax",
				}
			)
			.insert()
			.name
		)
		settings = frappe.get_single("Thai Tax Settings")
		for row in settings.company_accounts:
			if row.company == self.company:
				row.sales_tax_account = self.vat_account
				row.sales_tax_account_undue = undue_account
		settings.save()
		invoice = self.make_invoice(submit=False)
		invoice.taxes[0].account_head = undue_account
		invoice.save()
		invoice.submit()
		payment = self.sign(self.make_payment(invoice), "_Test RC")
		tax_invoice = frappe.get_doc(
			"Sales Tax Invoice", {"voucher_type": "Payment Entry", "voucher_no": payment.name}
		)
		line = self.server.doc_data["line_item_information"][0]
		self.assertEqual(line["product_code"], tax_invoice.name)
		self.assertEqual(line["line_tax_type_code"], "VAT")
		self.assertEqual(line["line_tax_rate"], 7)
		self.assertEqual(line["line_base_amount"], tax_invoice.tax_base)
		self.assertEqual(line["line_tax_amount"], tax_invoice.tax_amount)

	def test_replacement_of_paid_invoice(self):
		invoice = self.make_invoice()
		self.make_payment(invoice)
		self.sign(invoice)
		name = etax_service.create_replacement(
			"Sales Invoice", invoice.name, "TIVC01", "Wrong name"
		)
		replacement = frappe.get_doc("Sales Invoice", name)
		self.assertEqual(replacement.posting_date, invoice.posting_date)

	def test_only_customer_receipt(self):
		payment = frappe._dict(
			doctype="Payment Entry",
			docstatus=1,
			payment_type="Pay",
			party_type="Supplier",
			name="X",
		)
		self.assertRaises(
			frappe.ValidationError,
			etax_service.validate_before_sign,
			payment,
			frappe.get_doc("eTax Document Type", "_Test RC"),
		)

	# -- processing

	def test_processing_document_is_updated_by_scheduler(self):
		self.server.status = "Processing"
		payment = self.sign(self.make_payment(self.make_invoice()), "_Test RC")
		self.assertEqual(payment.etax_status, "Processing")
		self.assertRaises(frappe.ValidationError, payment.cancel)
		etax_service.update_processing_documents()
		payment.reload()
		self.assertEqual(payment.etax_status, "Success")
		self.assertTrue(
			frappe.db.exists(
				"File", {"attached_to_name": payment.name, "file_name": ("like", "%signed.pdf")}
			)
		)

	def test_unknown_server_status_is_processing(self):
		self.server.status = "Draft"
		self.assertEqual(self.sign(self.make_invoice()).etax_status, "Processing")

	# -- remaining paths

	def test_sign_with_erpnext_print_format(self):
		print_format = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "_Test eTax Print",
				"doc_type": "Sales Invoice",
				"standard": "No",
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": "<p>{{ doc.name }}</p>",
			}
		).insert()
		etax_doctype = frappe.get_doc("eTax Document Type", "_Test INV")
		etax_doctype.template_source = "ERPNext"
		etax_doctype.print_format = print_format.name
		etax_doctype.save()
		self.assertFalse(etax_doctype.server_print_format)
		invoice = self.make_invoice()
		with patch("frappe.utils.pdf.get_pdf", return_value=b"%PDF rendered") as get_pdf:
			self.sign(invoice)
		self.assertIn(invoice.name, get_pdf.call_args[0][0])
		data = self.server.requests[-1]["data"]
		self.assertEqual(data["form_type"], etax_service.FORM_TYPE_ERPNEXT)
		self.assertEqual(data["form_name"], "_Test eTax Print")
		self.assertEqual(base64.b64decode(data["pdf_content"]), b"%PDF rendered")

	def test_sign_list_of_documents(self):
		signed = self.sign(self.make_invoice())
		invoices = [self.make_invoice(), signed, self.make_invoice()]
		result = etax_service.sign_etax_documents(
			"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
		)
		self.assertEqual(result[invoices[0].name], "Success")
		self.assertIn("already Success", result[signed.name])
		self.assertEqual(result[invoices[2].name], "Success")

	def test_refresh_etax_status(self):
		self.server.status = "Processing"
		invoice = self.sign(self.make_invoice())
		self.assertEqual(
			etax_service.refresh_etax_status("Sales Invoice", invoice.name), "Success"
		)
		# Nothing to refresh
		self.assertFalse(etax_service.update_processing_document(invoice.reload()))

	def test_processing_without_server_document(self):
		self.server.status = "Processing"
		invoice = self.sign(self.make_invoice())
		with patch.object(
			etax_service.requests, "get", return_value=FakeResponse({"data": []})
		):
			self.assertFalse(etax_service.update_processing_document(invoice))
		invoice.db_set("etax_transaction_code", None)
		self.assertFalse(etax_service.update_processing_document(invoice))

	def test_scheduler_error_keeps_processing(self):
		self.server.status = "Processing"
		invoice = self.sign(self.make_invoice())
		with (
			patch.object(etax_service.requests, "get", side_effect=Exception("timeout")),
			patch.object(etax_service.frappe.db, "rollback") as rollback,
		):
			etax_service.update_processing_documents()
		rollback.assert_called()
		self.assertEqual(invoice.reload().etax_status, "Processing")

	def test_signed_file_download_failure_keeps_status(self):
		with patch.object(etax_service.requests, "get", side_effect=Exception("timeout")):
			invoice = self.sign(self.make_invoice())
		self.assertEqual(invoice.etax_status, "Success")
		self.assertFalse(frappe.db.exists("File", {"attached_to_name": invoice.name}))

	def test_error_message_of_non_json_response(self):
		response = FakeResponse(status_code=502)
		response.json = lambda: (_ for _ in ()).throw(ValueError())
		response.text = "Bad Gateway"
		self.assertEqual(etax_service.get_error_message(response), "Bad Gateway")
		response = FakeResponse(
			{"_server_messages": json.dumps(["plain text"])}, status_code=417
		)
		self.assertEqual(etax_service.get_error_message(response), "plain text")

	def test_non_vat_charge_is_not_line_tax(self):
		invoice = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 100}], submit=False
		)
		invoice.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": self.vat_account,
				"description": "Shipping",
				"tax_amount": 50,
			},
		)
		invoice.save()
		line = self.lines(invoice)[0]
		self.assertEqual(line["line_tax_rate"], 7)
		self.assertEqual(line["line_tax_amount"], 7)

	def test_sign_validation_of_configuration(self):
		self.assertTrue(etax_service.is_etax_enabled(self.company))
		self.assertRaises(
			frappe.ValidationError,
			etax_service.validate_before_sign,
			frappe._dict(doctype="Journal Entry", name="X"),
			None,
		)
		invoice = self.make_invoice()
		frappe.db.set_value("Customer", self.customer, "tax_id", "")
		self.assertRaises(frappe.ValidationError, self.sign, invoice)
		frappe.db.set_value("Customer", self.customer, "tax_id", "0105559999999")
		frappe.db.set_value("Company", self.company, "tax_id", "")
		self.assertRaises(frappe.ValidationError, self.sign, invoice)
		self.assertRaises(
			frappe.ValidationError, self.set_connection, replacement_lock_day=32
		)

	def test_replacement_validation(self):
		invoice = self.make_invoice()
		self.assertRaises(
			frappe.ValidationError,
			etax_service.create_replacement,
			"Sales Invoice",
			invoice.name,
			"TIVC01",
			"x",
		)
		self.sign(invoice)
		name = etax_service.create_replacement(
			"Sales Invoice", invoice.name, "TIVC01", "Wrong name"
		)
		replacement = frappe.get_doc("Sales Invoice", name)
		replacement.submit()
		# The replacement keeps the document type code of the original
		replacement.db_set("etax_document_type", None)
		self.assertRaises(frappe.ValidationError, self.sign, replacement, "_Test BILL")
		# Its purpose code must apply to the document type code
		replacement.db_set({"etax_purpose_code": "RCTC01", "etax_purpose": "Wrong name"})
		self.assertRaises(frappe.ValidationError, self.sign, replacement)

	def test_receipt_without_lines_is_rejected(self):
		"""An advance payment has no tax invoice nor paid invoice to send"""
		payment = get_payment_entry("Sales Invoice", self.make_invoice().name)
		payment.references = []
		payment.reference_no = "ADV"
		payment.reference_date = today()
		payment.insert()
		payment.submit()
		self.assertEqual(payment.unallocated_amount, payment.paid_amount)
		with self.assertRaisesRegex(frappe.ValidationError, "no e-Tax line items found"):
			self.sign(payment, "_Test RC")
		self.assertEqual(self.server.requests, [])
