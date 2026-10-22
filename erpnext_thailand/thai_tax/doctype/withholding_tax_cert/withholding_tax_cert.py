# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WithholdingTaxCert(Document):
	def on_update(self):
		self.update_payment_entry_wht_status()
		# Voucher changed, also refresh the previously linked payment
		before = self.get_doc_before_save()
		if before and (before.voucher_type, before.voucher_no) != (self.voucher_type, self.voucher_no):
			update_payment_entry_wht_status(before.voucher_type, before.voucher_no)

	def on_submit(self):
		self.update_payment_entry_wht_status()

	def on_cancel(self):
		self.update_payment_entry_wht_status()

	def after_delete(self):
		self.update_payment_entry_wht_status()

	def update_payment_entry_wht_status(self):
		update_payment_entry_wht_status(self.voucher_type, self.voucher_no)


def update_payment_entry_wht_status(voucher_type, voucher_no):
	"""Issued if any linked cert is submitted, otherwise Not Issued"""
	if voucher_type != "Payment Entry" or not voucher_no:
		return
	if not frappe.db.exists("Payment Entry", voucher_no):
		return
	docstatus = frappe.get_all(
		"Withholding Tax Cert",
		filters={"voucher_type": voucher_type, "voucher_no": voucher_no},
		pluck="docstatus",
	)
	status = "Issued" if 1 in docstatus else "Not Issued"
	frappe.db.set_value("Payment Entry", voucher_no, "wht_status", status, update_modified=False)
