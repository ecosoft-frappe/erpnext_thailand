# Copyright (c) 2026, Ecosoft and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Document type code that a credit/debit note must use
ADJUSTMENT_CODES = {"Credit Note": "81", "Debit Note": "80"}
# Receipts: ใบรับ (ใบเสร็จรับเงิน) and ใบเสร็จรับเงิน/ใบกำกับภาษี
RECEIPT_CODES = ("T01", "T03")


def get_print_doctype(applies_to):
	"""DocType of the document printed for this e-Tax document type"""
	return "Payment Entry" if applies_to == "Payment Entry" else "Sales Invoice"


class eTaxDocumentType(Document):
	def validate(self):
		if self.template_source == "ERPNext":
			self.server_print_format = None
		else:
			self.print_format = None
		self.validate_document_type_code()
		self.validate_print_format()

	def validate_document_type_code(self):
		code = ADJUSTMENT_CODES.get(self.applies_to)
		if code and self.document_type_code != code:
			frappe.throw(
				_("{0} must use document type code {1}").format(_(self.applies_to), code)
			)
		if (
			self.applies_to == "Payment Entry" and self.document_type_code not in RECEIPT_CODES
		):
			frappe.throw(_("Payment Entry must use document type code T01 or T03"))
		if not code and self.document_type_code in ADJUSTMENT_CODES.values():
			frappe.throw(
				_("Document type code {0} is only for credit and debit notes").format(
					self.document_type_code
				)
			)

	def validate_print_format(self):
		if not self.print_format:
			return
		doctype = get_print_doctype(self.applies_to)
		if frappe.db.get_value("Print Format", self.print_format, "doc_type") != doctype:
			frappe.throw(
				_("Print Format {0} is not for {1}").format(self.print_format, _(doctype))
			)
