# Copyright (c) 2024, FLO and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PaymentReceiptPaymentReference(Document):
	@property
	def mode_of_payment(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "mode_of_payment")
			if self.payment_entry
			else None
		)

	@property
	def party_bank_account(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "party_bank_account")
			if self.payment_entry
			else None
		)

	@property
	def company_bank_account(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "bank_account")
			if self.payment_entry
			else None
		)

	@property
	def chequereference_no(self):
		return frappe.db.get_value("Payment Entry", self.payment_entry, "reference_no") or ""

	@property
	def chequereference_date(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "reference_date")
			if self.payment_entry
			else None
		)

	@property
	def posting_date(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "posting_date")
			if self.payment_entry
			else None
		)

	@property
	def paid_amount(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "paid_amount") or 0
			if self.payment_entry
			else 0
		)

	@property
	def status(self):
		return (
			frappe.db.get_value("Payment Entry", self.payment_entry, "status")
			if self.payment_entry
			else None
		)
