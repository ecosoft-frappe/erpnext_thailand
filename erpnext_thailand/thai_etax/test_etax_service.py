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
					# The default groups of a new site may be group nodes
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}),
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
				"address_line2": "Soi 1",
				"city": "Suriyawong",
				"county": "Bang Rak",
				"state": "Bangkok",
				"pincode": "10500",
				"country": "Thailand",
				"is_primary_address": 1,
				"links": [{"link_doctype": "Customer", "link_name": cls.customer}],
			}
		).insert()
		for item_code in ("_Test eTax A", "_Test eTax B", "_Test eTax C"):
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": item_code,
						"item_group": frappe.db.get_value("Item Group", {"is_group": 0}),
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
			("_Test RC TAX", "Payment Entry", "T03"),
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
		# Runs after the rollback, the cached settings may be those saved by the test
		self.addCleanup(frappe.clear_document_cache, "Thai Tax Settings", "Thai Tax Settings")
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
		for url in ("etax.test", "https://", "ftp://etax.test"):
			connection.server_url = url
			self.assertRaises(frappe.ValidationError, connection.save)
		connection.reload()
		connection.server_url = f" {SERVER}/ "
		connection.save()
		self.assertEqual(connection.server_url, SERVER)

	def test_custom_fields_and_master_data(self):
		self.assertTrue(frappe.get_meta("Sales Invoice").has_field("etax_status"))
		self.assertTrue(frappe.get_meta("Payment Entry").has_field("etax_status"))
		self.assertTrue(frappe.get_meta("Sales Invoice Item").has_field("skip_etax"))
		self.assertTrue(frappe.get_meta("Customer").has_field("email_etax"))
		self.assertTrue(frappe.db.exists("eTax Document Type Code", "T02"))
		self.assertEqual(etax_service.get_purpose_codes("CDNG01"), ["81"])

	def test_master_data_keeps_user_changes(self):
		frappe.db.set_value("eTax Purpose Code", "CDNG01", "reason", "Changed by user")
		frappe.delete_doc("eTax Purpose Code", "CDNG02")
		etax_service.import_etax_master_data()
		self.assertEqual(
			frappe.db.get_value("eTax Purpose Code", "CDNG01", "reason"), "Changed by user"
		)
		self.assertTrue(frappe.db.exists("eTax Purpose Code", "CDNG02"))
		self.assertEqual(etax_service.get_purpose_codes("CDNG02"), ["81"])

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
		self.assertEqual(data["buyer_address_line3"], "Suriyawong Bang Rak Bangkok")
		# The district, the city of a Thai address is the sub-district
		self.assertEqual(data["buyer_city_name"], "Bang Rak")
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

	def test_buyer_branch_from_address(self):
		"""A customer with several branches sends the branch of the invoice address"""
		branch = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "eTax Buyer Branch",
				"address_type": "Billing",
				"address_line1": "1 Sathorn Road",
				"city": "Bangkok",
				"country": "Thailand",
				"branch_code": "00003",
				"links": [{"link_doctype": "Customer", "link_name": self.customer}],
			}
		).insert()
		self.sign(self.make_invoice(customer_address=branch.name))
		self.assertEqual(self.server.doc_data["buyer_branch_id"], "00003")
		# The tax ID falls back to the customer's
		self.assertEqual(self.server.doc_data["buyer_tax_id"], "0105559999999")
		branch.db_set("tax_id", "0105558888888")
		frappe.db.set_value("Customer", self.customer, "tax_id", "")
		self.sign(self.make_invoice(customer_address=branch.name))
		self.assertEqual(self.server.doc_data["buyer_tax_id"], "0105558888888")
		# A receipt has no address, it sends the branch of its invoice
		invoice = self.make_invoice(customer_address=branch.name)
		self.sign(self.make_payment(invoice), "_Test RC")
		self.assertEqual(self.server.doc_data["buyer_branch_id"], "00003")
		self.assertEqual(self.server.doc_data["buyer_tax_id"], "0105558888888")

	def test_tax_id_and_branch_are_cleaned(self):
		"""Tax ID and branch code are sent as digits, as typed with dashes or spaces"""
		frappe.db.set_value(
			"Customer", self.customer, {"tax_id": "0-1055-59999-99-9", "branch_code": "2"}
		)
		frappe.db.set_value("Company", self.company, "tax_id", "0 1055 51234 56 7")
		self.sign(self.make_invoice())
		data = self.server.doc_data
		self.assertEqual(data["buyer_tax_id"], "0105559999999")
		self.assertEqual(data["buyer_branch_id"], "00002")
		self.assertEqual(data["seller_tax_id"], "0105551234567")
		self.assertEqual(etax_service.clean_branch_code("สำนักงานใหญ่"), "00000")
		self.assertEqual(etax_service.clean_branch_code("Head Office"), "00000")
		# Not a Thai tax ID or branch code: stopped before anything is sent
		requests = len(self.server.requests)
		frappe.db.set_value("Customer", self.customer, "tax_id", "010555999999")
		self.assertRaisesRegex(
			frappe.ValidationError, "13 digits", self.sign, self.make_invoice()
		)
		frappe.db.set_value(
			"Customer", self.customer, {"tax_id": "0105559999999", "branch_code": "B01"}
		)
		self.assertRaisesRegex(
			frappe.ValidationError, "5 digits", self.sign, self.make_invoice()
		)
		frappe.db.set_value("Customer", self.customer, "branch_code", "00002")
		frappe.db.set_value("Company", self.company, "tax_id", "TH0105551234567")
		self.assertRaisesRegex(
			frappe.ValidationError, "13 digits", self.sign, self.make_invoice()
		)
		self.assertEqual(len(self.server.requests), requests)

	def test_send_mail_needs_buyer_email(self):
		frappe.db.set_value("Customer", self.customer, "email_etax", "")
		self.sign(self.make_invoice())
		self.assertEqual(self.server.doc_data["send_mail"], "N")

	def test_etax_log_permissions(self):
		etax_service.add_etax_log_permissions()
		etax_service.add_etax_log_permissions()  # once per role
		for role in etax_service.ETAX_LOG_ROLES:
			filters = {"parent": "Integration Request", "role": role}
			self.assertEqual(frappe.db.count("Custom DocPerm", filters), 1)
		user = frappe.get_doc(
			{"doctype": "User", "email": "etax-accounts@example.com", "first_name": "eTax"}
		).insert()
		user.add_roles("Accounts User")
		etax_log = frappe._dict(integration_request_service=etax_service.INTEGRATION_SERVICE)
		other_log = frappe._dict(integration_request_service="Stripe")
		self.assertIsNone(etax_service.has_etax_log_permission(etax_log, user=user.name))
		self.assertFalse(etax_service.has_etax_log_permission(other_log, user=user.name))
		self.assertIn("e-Tax", etax_service.get_etax_log_conditions(user.name))
		self.assertEqual(etax_service.get_etax_log_conditions("Administrator"), "")
		self.assertIsNone(
			etax_service.has_etax_log_permission(other_log, user="Administrator")
		)

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

	def test_line_taxes_add_up_to_document_tax(self):
		"""Taxes of each item code rounded alone would be 0.70 + 0.70, not 1.41"""
		invoice = self.make_invoice(
			[
				{"item_code": "_Test eTax A", "qty": 1, "rate": 10.05},
				{"item_code": "_Test eTax B", "qty": 1, "rate": 10.05},
			],
			submit=False,
		)
		lines = self.lines(invoice)
		self.assertEqual(invoice.total_taxes_and_charges, 1.41)
		self.assertEqual([line["line_tax_amount"] for line in lines], [0.70, 0.71])
		self.assertEqual([line["line_total_amount"] for line in lines], [10.75, 10.76])

	def make_zero_tax_template(self):
		return frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test eTax Zero",
				"company": self.company,
				"taxes": [{"tax_type": self.vat_account, "tax_rate": 0}],
			}
		).insert()

	def test_zero_rated_item_price_with_included_vat(self):
		"""VAT included in the rate is removed only from the rows that have VAT"""
		self.assert_zero_rated_row("_Test eTax B")

	def test_zero_rated_row_of_same_item(self):
		"""ERPNext keeps the tax per item code, each row has the rate of its item tax template"""
		self.assert_zero_rated_row("_Test eTax A")

	def test_not_applicable_vat_row_is_without_vat(self):
		"""An item tax template that sets VAT not applicable gives a line without VAT"""
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test eTax Exempt",
				"company": self.company,
				"taxes": [{"tax_type": self.vat_account, "not_applicable": 1}],
			}
		).insert()
		invoice = self.make_invoice(
			[
				{"item_code": "_Test eTax A", "qty": 1, "rate": 107},
				{
					"item_code": "_Test eTax A",
					"qty": 1,
					"rate": 100,
					"item_tax_template": template.name,
				},
			],
			included_in_print_rate=1,
			submit=False,
		)
		vat, exempt = self.lines(invoice)
		self.assertEqual(
			(vat["line_tax_type_code"], vat["line_base_amount"], vat["line_tax_amount"]),
			("VAT", 100, 7),
		)
		self.assertEqual(
			(
				exempt["line_tax_type_code"],
				exempt["product_price"],
				exempt["line_base_amount"],
				exempt["line_tax_amount"],
			),
			("FRE", 100, 100, 0),
		)

	def assert_zero_rated_row(self, zero_item_code):
		template = self.make_zero_tax_template()
		invoice = self.make_invoice(
			[
				{"item_code": "_Test eTax A", "qty": 1, "rate": 107},
				{
					"item_code": zero_item_code,
					"qty": 1,
					"rate": 100,
					"item_tax_template": template.name,
				},
			],
			included_in_print_rate=1,
			submit=False,
		)
		vat, zero = self.lines(invoice)
		self.assertEqual((vat["product_price"], vat["line_base_amount"]), (100, 100))
		self.assertEqual((vat["line_tax_rate"], vat["line_tax_amount"]), (7, 7))
		self.assertEqual((zero["product_price"], zero["line_base_amount"]), (100, 100))
		self.assertEqual((zero["line_tax_rate"], zero["line_tax_amount"]), (0, 0))
		self.assertEqual(zero["line_allowance_actual_amount"], 0)

	def make_foreign_invoice(self, items, conversion_rate):
		"""Invoice in a currency other than the company currency, return (invoice, currency)"""
		company_currency = frappe.db.get_value("Company", self.company, "default_currency")
		currency = "EUR" if company_currency == "USD" else "USD"
		receivable = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "_Test eTax Debtors",
				"company": self.company,
				"parent_account": frappe.db.get_value(
					"Account",
					{"company": self.company, "is_group": 1, "root_type": "Asset"},
				),
				"account_type": "Receivable",
				"account_currency": currency,
			}
		).insert()
		# The test customer may already have entries in company currency
		customer = frappe.copy_doc(frappe.get_doc("Customer", self.customer))
		customer.customer_name = "_Test eTax Foreign Customer"
		customer.insert()
		invoice = self.make_invoice(
			items,
			customer=customer.name,
			currency=currency,
			conversion_rate=conversion_rate,
			debit_to=receivable.name,
		)
		self.assertEqual(invoice.conversion_rate, conversion_rate)
		return invoice, currency

	def test_foreign_currency_lines(self):
		"""ERPNext keeps item taxes in company currency, lines are in the invoice currency"""
		invoice, currency = self.make_foreign_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 100}], 35
		)
		self.assertEqual(invoice.base_total_taxes_and_charges, 245)
		(line,) = self.lines(invoice)
		self.assertEqual(line["line_base_amount"], 100)
		self.assertEqual(line["line_tax_amount"], 7)
		self.assertEqual(line["line_total_amount"], 107)
		self.assertEqual(line["line_allowance_actual_currency_code"], currency)
		self.assertEqual(etax_service.get_currency(invoice), currency)

	def test_row_wise_rounded_line_taxes(self):
		"""Round Tax Amount Row-wise: the line taxes are those of ERPNext, i.e., 0.70 each.

		The item taxes in company currency (23.45 = 0.7035 x 33.3333) converted back
		and rounded cumulatively would be 0.70 + 0.71 + 0.69.
		"""
		frappe.db.set_single_value("Accounts Settings", "round_row_wise_tax", 1)
		self.addCleanup(
			frappe.db.set_single_value, "Accounts Settings", "round_row_wise_tax", 0
		)
		invoice, currency = self.make_foreign_invoice(
			[
				{"item_code": code, "qty": 1, "rate": 10.05}
				for code in ("_Test eTax A", "_Test eTax B", "_Test eTax C")
			],
			33.3333,
		)
		self.assertEqual(invoice.total_taxes_and_charges, 2.10)
		self.assertEqual(
			[line["line_tax_amount"] for line in self.lines(invoice)], [0.70] * 3
		)

	def test_tax_invoice_receipt_currency(self):
		"""Sales Tax Invoices of a receipt are in company currency"""
		payment = frappe._dict(
			doctype="Payment Entry",
			name="X",
			company=self.company,
			paid_from_account_currency="USD",
		)
		self.assertEqual(etax_service.get_currency(payment), "USD")
		with patch.object(etax_service, "get_payment_tax_invoices", return_value=[{}]):
			self.assertEqual(
				etax_service.get_currency(payment),
				frappe.db.get_value("Company", self.company, "default_currency"),
			)

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

	def get_etax_logs(self, doc):
		return frappe.get_all(
			"Integration Request",
			filters={
				"integration_request_service": etax_service.INTEGRATION_SERVICE,
				"reference_doctype": doc.doctype,
				"reference_docname": doc.name,
			},
			fields=["request_description", "status", "url", "data", "output", "error"],
			order_by="creation",
		)

	def test_requests_are_logged(self):
		self.server.status = "Processing"
		invoice = self.sign(self.make_invoice())
		etax_service.refresh_etax_status("Sales Invoice", invoice.name)
		sign_log, status_log = self.get_etax_logs(invoice)
		self.assertEqual(sign_log.request_description, "Sign e-Tax")
		self.assertEqual(sign_log.status, "Completed")
		self.assertEqual(sign_log.url, SERVER + etax_service.SIGN_ROUTE)
		data = json.loads(sign_log.data)
		self.assertEqual(data["doc_data"]["document_id"], invoice.name)
		# The authorization header (API secret) is not kept
		self.assertNotIn("token key:secret", sign_log.data)
		self.assertEqual(json.loads(sign_log.output)["message"]["transaction_code"], "TX1")
		self.assertEqual(status_log.request_description, "Refresh e-Tax Status")
		self.assertEqual(status_log.status, "Completed")
		# Shown in the connections of the document
		data = frappe.get_meta("Sales Invoice").get_dashboard_data()
		self.assertEqual(
			data.non_standard_fieldnames["Integration Request"], "reference_docname"
		)
		self.assertEqual(
			data.dynamic_links["reference_docname"], ["Sales Invoice", "reference_doctype"]
		)

	def test_failed_requests_are_logged(self):
		self.server.post_response = FakeResponse(
			{"exception": "Not permitted"}, status_code=403
		)
		invoice = self.sign(self.make_invoice())
		with patch.object(
			etax_service.requests,
			"post",
			side_effect=etax_service.requests.Timeout("timeout"),
		):
			self.sign(invoice)
		http_error, timeout = self.get_etax_logs(invoice)
		self.assertEqual(http_error.status, "Failed")
		self.assertEqual(json.loads(http_error.error), {"exception": "Not permitted"})
		self.assertFalse(http_error.output)
		self.assertEqual(timeout.status, "Failed")
		self.assertEqual(json.loads(timeout.error), "timeout")

	def test_sign_validation(self):
		draft = self.make_invoice(submit=False)
		self.assertRaises(frappe.ValidationError, self.sign, draft)
		invoice = self.make_invoice()
		self.assertRaises(frappe.ValidationError, self.sign, invoice, "_Test CN")
		self.set_connection(enabled=0)
		self.assertRaises(frappe.ValidationError, self.sign, invoice)
		self.assertEqual(self.server.requests, [])

	def test_sign_needs_buyer_address(self):
		"""The e-Tax server requires the country of the buyer address"""
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "_Test eTax No Address",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}),
				"tax_id": "0105559999998",
			}
		).insert()
		invoice = self.make_invoice(customer=customer.name)
		self.assertRaisesRegex(
			frappe.ValidationError, "address of customer", self.sign, invoice
		)
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
		# The customer of a receipt is its party
		payment = self.make_payment(invoices[1])
		self.assertRaisesRegex(
			frappe.ValidationError,
			f"{payment.name}: {self.customer}",
			etax_service.sign_etax_documents,
			"Payment Entry",
			json.dumps([payment.name]),
			"_Test RC",
		)
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
		# Not a replacement, the document type is selected again when signing
		self.assertFalse(amended.etax_document_type)
		self.assertFalse(amended.etax_document_type_code)
		# Not a replacement, the original was never signed: no reference is sent
		amended.submit()
		self.server.status = "Success"
		self.sign(amended)
		data = self.server.doc_data
		self.assertFalse(data["ref_document_id"])
		self.assertFalse(data["ref_document_type_code"])

	# -- credit and debit notes

	def test_credit_note_of_invoice_with_skipped_line(self):
		"""Original and adjusted amounts are those sent as e-Tax, without the Skip e-Tax lines"""
		invoice = self.sign(
			self.make_invoice(
				[
					{"item_code": "_Test eTax A", "qty": 1, "rate": 300},
					{"item_code": "_Test eTax B", "qty": 1, "rate": 20, "skip_etax": 1},
				]
			)
		)
		self.assertEqual(self.server.doc_data["final_amount_untaxed"], 300)
		credit_note = make_sales_return(invoice.name)
		credit_note.items[0].qty = -1
		credit_note.items[0].rate = 100
		credit_note.items[1].qty = -1
		credit_note.etax_purpose_code = "CDNG02"
		credit_note.insert()
		credit_note.submit()
		self.sign(credit_note, "_Test CN")
		data = self.server.doc_data
		self.assertEqual(data["original_amount_untaxed"], 300)
		self.assertEqual(data["adjust_amount_untaxed"], 100)
		self.assertEqual(data["final_amount_untaxed"], 200)
		self.assertEqual(
			sum(line["line_base_amount"] for line in data["line_item_information"]), 100
		)

	def test_note_without_invoice(self):
		"""A credit/debit note sent as e-Tax must refer to its invoice"""
		credit_note = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": -1, "rate": 100}],
			is_return=1,
			etax_purpose_code="CDNG02",
		)
		self.assertRaisesRegex(
			frappe.ValidationError, "Return Against", self.sign, credit_note, "_Test CN"
		)
		self.assertEqual(self.server.requests, [])

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
		self.assertEqual(data["final_amount_untaxed"], flt(invoice.net_total - 100.33, 2))
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
		self.assertEqual(data["final_amount_untaxed"], flt(invoice.net_total + 120, 2))

	def test_price_adjustment_note_has_no_allowance(self):
		"""The price list rate copied from the invoice is not a discount of the note"""
		invoice = self.sign(self.make_invoice())
		credit_note = make_sales_return(invoice.name)
		credit_note.items = credit_note.items[:1]
		credit_note.items[0].update({"qty": -1, "rate": 30, "discount_percentage": 70})
		credit_note.etax_purpose_code = "CDNG04"
		credit_note.insert()
		credit_note.submit()
		self.sign(credit_note, "_Test CN")
		line = self.server.doc_data["line_item_information"][0]
		self.assertEqual(line["product_price"], 30)
		self.assertEqual(line["line_base_amount"], 30)
		self.assertEqual(line["line_allowance_actual_amount"], 0)

	def test_sign_without_etax_lines(self):
		invoice = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 100, "skip_etax": 1}]
		)
		self.assertRaises(frappe.ValidationError, self.sign, invoice)
		self.assertFalse(self.server.requests)

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
		# The signed files of the original are not copied to the replacement
		def files(name):
			return frappe.get_all(
				"File", filters={"attached_to_doctype": "Sales Invoice", "attached_to_name": name}
			)

		self.assertFalse(files(name))
		self.assertEqual(len(files(invoice.name)), 2)
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

	def test_no_replacement_for_credit_note(self):
		invoice = self.sign(self.make_invoice())
		credit_note = make_sales_return(invoice.name)
		credit_note.etax_purpose_code = "CDNG05"
		credit_note.insert()
		credit_note.submit()
		self.sign(credit_note, "_Test CN")
		self.assertRaises(
			frappe.ValidationError,
			etax_service.create_replacement,
			"Sales Invoice",
			credit_note.name,
			"CDNG05",
			"Returned goods",
		)
		self.assertEqual(credit_note.reload().docstatus, 1)

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
		# VAT was invoiced, the receipt acknowledges the amount paid, VAT included
		(line,) = data["line_item_information"]
		self.assertEqual(line["product_code"], invoice.name)
		self.assertEqual(line["line_tax_type_code"], "FRE")
		self.assertEqual(line["line_total_amount"], payment.references[0].allocated_amount)
		self.assertEqual(
			line["line_total_amount"], invoice.rounded_total or invoice.grand_total
		)
		self.assertEqual(data["final_amount_untaxed"], line["line_base_amount"])

	def test_receipt_with_credit_note(self):
		"""A credit note set off in the receipt is an allowance line, as a deposit deduction"""
		invoice = self.make_invoice()
		credit_note = make_sales_return(invoice.name)
		credit_note.items = credit_note.items[:1]
		credit_note.items[0].qty = -1
		credit_note.insert()
		credit_note.submit()
		payment = get_payment_entry("Sales Invoice", invoice.name)
		payment.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": credit_note.name,
				"total_amount": credit_note.grand_total,
				"outstanding_amount": credit_note.grand_total,
				"allocated_amount": credit_note.grand_total,
			},
		)
		payment.paid_amount = payment.received_amount = sum(
			ref.allocated_amount for ref in payment.references
		)
		payment.update({"reference_no": "REF", "reference_date": today()})
		payment.insert()
		payment.submit()
		self.sign(payment, "_Test RC")
		data = self.server.doc_data
		lines = {line["product_code"]: line for line in data["line_item_information"]}
		note = lines[credit_note.name]
		self.assertEqual(note["product_price"], 0)
		self.assertEqual(note["line_base_amount"], credit_note.grand_total)
		self.assertEqual(note["line_allowance_charge_ind"], "false")
		self.assertEqual(note["line_allowance_actual_amount"], -credit_note.grand_total)
		self.assertEqual(lines[invoice.name]["line_allowance_actual_amount"], 0)
		self.assertEqual(data["final_amount_untaxed"], payment.paid_amount)
		# The text does not depend on the language of the user who signs
		frappe.local.lang = "th"
		try:
			names = [
				line["product_name"]
				for line in etax_service.get_payment_line_items(payment.reload())
			]
		finally:
			frappe.local.lang = "en"
		self.assertEqual(
			names, [line["product_name"] for line in data["line_item_information"]]
		)

	def test_partial_receipt(self):
		invoice = self.make_invoice()
		payment = get_payment_entry("Sales Invoice", invoice.name)
		payment.update({"reference_no": "REF", "reference_date": today()})
		payment.paid_amount = payment.received_amount = 50
		payment.references[0].allocated_amount = 50
		payment.insert()
		payment.submit()
		self.sign(payment, "_Test RC")
		(line,) = self.server.doc_data["line_item_information"]
		self.assertEqual(line["line_total_amount"], 50)
		self.assertEqual(self.server.doc_data["final_amount_untaxed"], 50)

	def test_tax_invoice_receipt_needs_due_vat(self):
		"""T03 is a tax invoice, without undue VAT the invoice was the tax invoice"""
		payment = self.make_payment(self.make_invoice())
		self.assertRaises(frappe.ValidationError, self.sign, payment, "_Test RC TAX")
		self.assertFalse(self.server.requests)

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

	def make_undue_invoice(self, items=None, included_in_print_rate=0):
		"""Invoice of a service, its VAT is due on payment"""
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
		# The rows of the ERPNext test companies are added before their records
		settings.flags.ignore_links = True
		settings.save()
		invoice = self.make_invoice(items, included_in_print_rate, submit=False)
		invoice.taxes[0].account_head = undue_account
		invoice.save()
		invoice.submit()
		return invoice

	def test_receipt_with_undue_tax_invoice(self):
		"""Undue VAT becomes due on payment, the receipt sends its Sales Tax Invoice"""
		invoice = self.make_undue_invoice()
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
		self.assertEqual(self.server.doc_data["final_amount_untaxed"], tax_invoice.tax_base)

	def test_undue_invoice_is_not_tax_invoice(self):
		"""The receipt is the tax invoice of undue VAT, the invoice can only be 380"""
		invoice = self.make_undue_invoice(included_in_print_rate=1)
		self.assertTrue(etax_service.has_undue_vat(invoice))
		self.assertFalse(etax_service.has_undue_vat(self.make_invoice(submit=False)))
		self.assertRaises(frappe.ValidationError, self.sign, invoice, "_Test INV")
		self.assertFalse(self.server.requests)
		self.sign(invoice, "_Test BILL")
		self.assertEqual(invoice.etax_status, "Success")
		self.assertEqual(self.server.doc_data["document_type_code"], "380")
		# Its credit note is not a tax document either, the receipt is the tax invoice
		credit_note = make_sales_return(invoice.name)
		credit_note.etax_purpose_code = "CDNG02"
		credit_note.etax_purpose = "Damaged goods"
		credit_note.insert()
		credit_note.submit()
		self.assertRaisesRegex(
			frappe.ValidationError,
			"credit or debit note is undue",
			self.sign,
			credit_note,
			"_Test CN",
		)
		frappe.db.set_value(
			"Thai Tax Settings Company",
			{"parent": "Thai Tax Settings", "company": self.company},
			"sales_tax_account_undue",
			self.vat_account,
		)
		frappe.clear_document_cache("Thai Tax Settings", "Thai Tax Settings")
		self.assertFalse(etax_service.has_undue_vat(self.make_invoice(submit=False)))

	def test_replacement_of_undue_tax_receipt(self):
		"""The Sales Tax Invoice of the receipt is cancelled with it, its replacement has a new one"""
		payment = self.sign(self.make_payment(self.make_undue_invoice()), "_Test RC TAX")
		tax_invoice = frappe.get_doc(
			"Sales Tax Invoice", {"voucher_type": "Payment Entry", "voucher_no": payment.name}
		)
		name = etax_service.create_replacement(
			"Payment Entry", payment.name, "TIVC01", "Wrong name"
		)
		self.assertEqual(
			frappe.db.get_value("Sales Tax Invoice", tax_invoice.name, "docstatus"), 2
		)
		replacement = frappe.get_doc("Payment Entry", name)
		replacement.submit()
		self.sign(replacement, "_Test RC TAX")
		self.assertEqual(replacement.etax_status, "Success")
		new_tax_invoice = frappe.get_doc(
			"Sales Tax Invoice",
			{"voucher_type": "Payment Entry", "voucher_no": name, "docstatus": 1},
		)
		data = self.server.doc_data
		self.assertEqual(data["ref_document_id"], payment.name)
		(line,) = data["line_item_information"]
		self.assertEqual(line["product_code"], new_tax_invoice.name)
		self.assertEqual(line["line_tax_amount"], tax_invoice.tax_amount)

	def test_partial_receipt_of_undue_vat(self):
		"""The Sales Tax Invoice of a partial payment keeps an unrounded base"""
		invoice = self.make_undue_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 100}]
		)
		payment = get_payment_entry("Sales Invoice", invoice.name)
		payment.references[
			0
		].allocated_amount = payment.paid_amount = payment.received_amount = 50
		payment.reference_no = "REF"
		payment.reference_date = today()
		payment.insert()
		payment.submit()
		self.assertNotEqual(
			frappe.db.get_value("Sales Tax Invoice", {"voucher_no": payment.name}, "tax_base"),
			46.73,
		)
		self.sign(payment, "_Test RC TAX")
		(line,) = self.server.doc_data["line_item_information"]
		self.assertEqual(line["product_price"], 46.73)
		self.assertEqual(line["line_base_amount"], 46.73)
		self.assertEqual(line["line_tax_amount"], 3.27)
		self.assertEqual(line["line_total_amount"], 50)
		self.assertEqual(self.server.doc_data["final_amount_untaxed"], 46.73)

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
				"File", {"attached_to_name": payment.name, "file_name": ("like", "%_signed%.pdf")}
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
		# The log keeps the size of the PDF, not its content
		log = self.get_etax_logs(invoice)[-1]
		self.assertNotIn(data["pdf_content"], log.data)
		self.assertIn("characters of base64 PDF", json.loads(log.data)["pdf_content"])

	def test_document_type_validation(self):
		def make(applies_to, code, print_format=None):
			doc = frappe.new_doc("eTax Document Type")
			doc.update(
				{
					"applies_to": applies_to,
					"document_type_code": code,
					"template_source": "ERPNext" if print_format else "eTax Server",
					"print_format": print_format,
					"server_print_format": None if print_format else "X",
				}
			)
			doc.validate()

		self.assertRaises(frappe.ValidationError, make, "Credit Note", "80")
		self.assertRaises(frappe.ValidationError, make, "Debit Note", "T02")
		self.assertRaises(frappe.ValidationError, make, "Sales Invoice", "81")
		make("Credit Note", "81")
		print_format = frappe.db.get_value("Print Format", {"doc_type": "Sales Invoice"})
		make("Sales Invoice", "T02", print_format)
		self.assertRaises(frappe.ValidationError, make, "Payment Entry", "T01", print_format)
		# A receipt is T01 or T03
		self.assertRaisesRegex(
			frappe.ValidationError, "T01 or T03", make, "Payment Entry", "T02"
		)
		self.assertRaisesRegex(
			frappe.ValidationError, "T01 or T03", make, "Payment Entry", "388"
		)
		make("Payment Entry", "T03")

	def test_sign_list_of_documents(self):
		signed = self.sign(self.make_invoice())
		invoices = [self.make_invoice(), signed, self.make_invoice()]
		result = etax_service.sign_etax_documents(
			"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
		)
		self.assertEqual(result[invoices[0].name], "Success")
		self.assertIn("already Success", result[signed.name])
		self.assertEqual(result[invoices[2].name], "Success")

	def test_sign_list_continues_after_unexpected_error(self):
		"""A document that fails, i.e., PDF rendering, does not stop the others"""
		invoices = [self.make_invoice(), self.make_invoice()]
		prepare_payload = etax_service.prepare_payload

		def fail_first(doc, etax_doctype):
			if doc.name == invoices[0].name:
				raise OSError("wkhtmltopdf exited with code -6")
			return prepare_payload(doc, etax_doctype)

		with patch.object(etax_service, "prepare_payload", fail_first):
			result = etax_service.sign_etax_documents(
				"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
			)
		self.assertIn("wkhtmltopdf", result[invoices[0].name])
		self.assertFalse(invoices[0].reload().etax_status)
		self.assertEqual(result[invoices[1].name], "Success")

	def test_sign_list_in_background(self):
		"""Many documents are signed in background, the user is notified of the result"""
		invoices = [self.make_invoice(), self.make_invoice()]
		jobs = []
		with (
			patch.object(etax_service, "SIGN_NOW_LIMIT", 1),
			patch.object(
				etax_service.frappe,
				"enqueue",
				lambda method, **kwargs: jobs.append((method, kwargs)),
			),
		):
			result = etax_service.sign_etax_documents(
				"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
			)
		self.assertIsNone(result)
		self.assertFalse(self.server.requests)
		((method, kwargs),) = jobs
		self.assertEqual(kwargs["queue"], "long")
		method(kwargs["doctype"], kwargs["names"], kwargs["etax_document_type"])
		self.assertEqual(
			[inv.reload().etax_status for inv in invoices], ["Success", "Success"]
		)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"for_user": frappe.session.user, "subject": "e-Tax: 2 of 2 Sales Invoice signed"},
			)
		)

	def test_sign_list_of_payments(self):
		"""Payment Entry list: each receipt is signed on its own, a rejected one does not stop the others"""
		signed = self.sign(self.make_payment(self.make_invoice()), "_Test RC")
		payments = [
			self.make_payment(self.make_invoice()),
			signed,
			self.make_payment(self.make_invoice()),
		]
		result = etax_service.sign_etax_documents(
			"Payment Entry", json.dumps([pe.name for pe in payments]), "_Test RC"
		)
		self.assertEqual(result[payments[0].name], "Success")
		self.assertIn("already Success", result[signed.name])
		self.assertEqual(result[payments[2].name], "Success")
		for payment in payments:
			self.assertEqual(payment.reload().etax_status, "Success")
		# T03 needs undue VAT, the receipt is rejected before anything is sent
		requests = len(self.server.requests)
		payment = self.make_payment(self.make_invoice())
		result = etax_service.sign_etax_documents(
			"Payment Entry", json.dumps([payment.name]), "_Test RC TAX"
		)
		self.assertIn("no VAT is due", result[payment.name])
		self.assertFalse(payment.reload().etax_status)
		self.assertEqual(len(self.server.requests), requests)

	def test_sign_locks_document(self):
		"""Two requests for the same document cannot both send it, the second waits for the lock"""
		invoice = self.make_invoice()
		get_value = frappe.db.get_value
		with patch.object(frappe.db, "get_value", side_effect=get_value) as spy:
			self.sign(invoice)
		self.assertIn(
			(("Sales Invoice", invoice.name, "etax_status"), {"for_update": True}),
			[(c.args, c.kwargs) for c in spy.call_args_list],
		)
		# The committed status of the locking read decides, after the PDF is rendered
		invoice = self.make_invoice()
		with patch.object(
			frappe.db,
			"get_value",
			side_effect=lambda *a, **k: "Success" if k.get("for_update") else get_value(*a, **k),
		):
			self.assertRaisesRegex(frappe.ValidationError, "already Success", self.sign, invoice)
		self.assertEqual(len(self.server.requests), 1)
		self.assertFalse(invoice.reload().etax_document_type)

	def test_sign_list_after_commit(self):
		"""A document failing after a commit (i.e., rendering the PDF) does not stop the list"""
		invoices = [self.make_invoice(), self.make_invoice()]
		lock = etax_service.lock_before_sign

		def fail_first(doc):
			if doc.name == invoices[0].name:
				raise frappe.ValidationError("already Success")
			return lock(doc)

		def rollback(save_point=None, **kwargs):
			# The commit of the access log released the savepoint
			if save_point:
				raise Exception("SAVEPOINT etax_sign does not exist")

		with (
			patch.object(etax_service, "lock_before_sign", side_effect=fail_first),
			patch.object(etax_service.frappe.db, "rollback", side_effect=rollback) as spy,
		):
			result = etax_service.sign_etax_documents(
				"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
			)
		self.assertIn("already Success", result[invoices[0].name])
		self.assertEqual(result[invoices[1].name], "Success")
		# The savepoint is gone, the transaction of the failed document is rolled back
		self.assertEqual(
			[c.kwargs.get("save_point") for c in spy.call_args_list], ["etax_sign", None]
		)

	def test_sign_list_reports_permission_error(self):
		"""A document the user cannot sign is reported, the others are still signed"""
		invoices = [self.make_invoice(), self.make_invoice()]
		validate = etax_service.validate_before_sign

		def deny_second(doc, etax_doctype):
			if doc.name == invoices[1].name:
				raise frappe.PermissionError("Not permitted")
			return validate(doc, etax_doctype)

		with patch.object(etax_service, "validate_before_sign", side_effect=deny_second):
			result = etax_service.sign_etax_documents(
				"Sales Invoice", json.dumps([inv.name for inv in invoices]), "_Test INV"
			)
		self.assertEqual(result[invoices[0].name], "Success")
		self.assertIn("Not permitted", result[invoices[1].name])

	def test_refresh_etax_status(self):
		self.server.status = "Processing"
		invoice = self.sign(self.make_invoice())
		self.assertEqual(
			etax_service.refresh_etax_status("Sales Invoice", invoice.name), "Success"
		)
		# Nothing to refresh
		self.assertFalse(etax_service.update_processing_document(invoice.reload()))

	def test_still_processing_keeps_no_log(self):
		"""The scheduler checks every minute, a check that changes nothing is not kept"""
		self.server.status = "Processing"
		invoice = self.sign(self.make_invoice())
		logs = frappe.db.count("Integration Request", {"reference_docname": invoice.name})
		comments = frappe.db.count("Comment", {"reference_name": invoice.name})
		response = FakeResponse(
			{"data": [{"status": "Processing", "transaction_code": "TX1"}]}
		)
		with patch.object(etax_service.requests, "get", return_value=response):
			etax_service.update_processing_documents()
		self.assertEqual(invoice.reload().etax_status, "Processing")
		self.assertEqual(
			frappe.db.count("Integration Request", {"reference_docname": invoice.name}), logs
		)
		self.assertEqual(
			frappe.db.count("Comment", {"reference_name": invoice.name}), comments
		)
		# A change is kept
		etax_service.update_processing_documents()
		self.assertEqual(invoice.reload().etax_status, "Success")
		self.assertEqual(
			frappe.db.count("Integration Request", {"reference_docname": invoice.name}), logs + 1
		)

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
		with patch.object(etax_service.requests, "get", side_effect=Exception("timeout")):
			etax_service.update_processing_documents()
		# Only the failed update is rolled back, the error is logged
		self.assertEqual(invoice.reload().etax_status, "Processing")
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"method": f"e-Tax status update failed: Sales Invoice {invoice.name}"}
			)
		)

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

	def test_charges_are_lines_without_vat(self):
		"""Shipping and service charge rows are lines of their own, not the VAT of the items"""
		income_account = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Income", "is_group": 0}
		)
		invoice = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 100}], submit=False
		)
		invoice.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": income_account,
				"description": "Shipping",
				"tax_amount": 50,
			},
		)
		invoice.append(
			"taxes",
			{
				"charge_type": "On Net Total",
				"account_head": income_account,
				"description": "Service Charge",
				"rate": 10,
			},
		)
		invoice.save()
		item, shipping, service = self.lines(invoice)
		self.assertEqual((item["line_tax_rate"], item["line_tax_amount"]), (7, 7))
		self.assertEqual(
			(shipping["product_name"], shipping["line_base_amount"]), ("Shipping", 50)
		)
		self.assertEqual(
			(shipping["line_tax_type_code"], shipping["line_tax_amount"]), ("FRE", 0)
		)
		self.assertEqual((service["line_base_amount"], service["line_tax_amount"]), (10, 0))
		total = sum(line["line_total_amount"] for line in (item, shipping, service))
		self.assertEqual(total, invoice.grand_total)
		invoice.submit()
		self.sign(invoice)
		self.assertEqual(self.server.doc_data["final_amount_untaxed"], 160)
		# The credit note returns the charges too
		credit_note = make_sales_return(invoice.name)
		credit_note.etax_purpose_code = "CDNG02"
		credit_note.etax_purpose = "Damaged goods"
		credit_note.insert()
		credit_note.submit()
		self.sign(credit_note, "_Test CN")
		data = self.server.doc_data
		self.assertEqual(
			(
				data["original_amount_untaxed"],
				data["adjust_amount_untaxed"],
				data["final_amount_untaxed"],
			),
			(160, 160, 0),
		)

	def test_vat_on_previous_row_is_not_sent(self):
		"""VAT of a charge cannot be split between the lines, the charge must be an item line"""
		invoice = self.make_invoice(
			[{"item_code": "_Test eTax A", "qty": 1, "rate": 100}], submit=False
		)
		invoice.taxes[0].charge_type = "Actual"
		invoice.taxes[0].tax_amount = 7
		invoice.save()
		invoice.submit()
		self.assertRaisesRegex(
			frappe.ValidationError, "On Net Total only", self.sign, invoice
		)
		self.assertFalse(self.server.requests)

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
