# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WithholdingTaxCert(Document):
	def has_voucher(self):
		return self.voucher_type and self.voucher_no

	def validate_duplicate_wht_cert(self):
		wht_cert_count = frappe.db.count(
			"Withholding Tax Cert",
			{
				"voucher_type": self.voucher_type,
				"voucher_no": self.voucher_no,
				"docstatus": ["!=", 2]
			}
		)
		if wht_cert_count > 1:
			frappe.throw(_("Withholding Tax Cert has already been created for {} {}").format(
				self.voucher_type, self.voucher_no))

	def validate_voucher_is_submitted(self):
		voucher = frappe.get_doc(self.voucher_type, self.voucher_no)
		if voucher.docstatus != 1:
			frappe.throw(_("Please submit {} before submit this withholding tax cert.").format(
				voucher.name))

	def validate_wht_cert_matches_payment(self):
		if self.voucher_type == "Payment Entry":
			voucher = frappe.get_doc(self.voucher_type, self.voucher_no)
			payment_wht = {}
			for deduction in voucher.get("deductions"):
				base = deduction.get("withholding_tax_base", 0)
				amount = deduction.get("amount", 0)
				rate = 0
				wht_type = deduction.get("withholding_tax_type")
				if wht_type:
					rate = frappe.get_cached_value("Withholding Tax Type", wht_type, "percent")
				if rate not in payment_wht:
					payment_wht[rate] = {
						"tax_base": -base,
						"tax_amount": -amount,
					}
				else:
					payment_wht[rate].update({
						"tax_base": payment_wht[rate]["tax_base"] - base,
						"tax_amount": payment_wht[rate]["tax_amount"] - amount,
					})
			wht_cert = {}
			for item in self.withholding_tax_items:
				rate = item.tax_rate if item.tax_rate else 0
				if rate not in wht_cert:
					wht_cert[rate] = {
						"tax_base": item.tax_base,
						"tax_amount": item.tax_amount,
					}
				else:
					wht_cert[rate].update({
						"tax_base": wht_cert[rate]["tax_base"] + item.tax_base,
						"tax_amount": wht_cert[rate]["tax_amount"] + item.tax_amount,
					})
			if dict(sorted(payment_wht.items())) != dict(sorted(wht_cert.items())):
				frappe.throw(_("Withholding tax details in the certificate do not align with the payment deductions."))

	def on_update(self):
		if self.has_voucher():
			self.validate_duplicate_wht_cert()

	def before_submit(self):
		if self.has_voucher():
			self.validate_voucher_is_submitted()
			self.validate_wht_cert_matches_payment()
