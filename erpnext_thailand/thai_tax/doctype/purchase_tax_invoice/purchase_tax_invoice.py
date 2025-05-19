# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
from frappe.utils import add_months


class PurchaseTaxInvoice(Document):
    
	def submit(self):
		if self.against_voucher_type == "Payment Entry":
			frappe.db.set_value("Payment Entry", self.against_voucher, "has_purchase_tax_invoice", 1)
		super().submit()

	def cancel(self):
		if self.against_voucher_type == "Payment Entry":
			frappe.db.set_value("Payment Entry", self.against_voucher, "has_purchase_tax_invoice", 0)
		super().cancel()

	def validate(self):
		self.compute_report_date()

	def on_update_after_submit(self):
		if self.get_doc_before_save():  # Some change is made
			self.compute_report_date()
			if self.voucher_type and self.voucher_no:
				origin_doc = frappe.get_doc(self.voucher_type, self.voucher_no)
				if self.voucher_type == "Journal Entry":
					gl = frappe.get_doc("GL Entry", self.gl_entry)
					origin_doc = frappe.get_doc(
						"Journal Entry Tax Invoice Detail", gl.voucher_detail_no
					)
				if not origin_doc.get("split_tax_invoice", False):
					origin_doc.tax_invoice_number = self.number
					origin_doc.tax_invoice_date = self.date
					origin_doc.save(ignore_permissions=True)
				else: # find in Purchase Invoice Detail Tax Invoice
					dt = {
						"Purchase Invoice": "Purchase Invoice Tax Invoice Detail",
						"Expense Claim": "Expense Claim Tax Invoice Detail",
					}
					if self.voucher_type not in dt.keys():
						return
					row = frappe.get_doc(dt[self.voucher_type], self.splitted_tax_invoice)
					row.tax_invoice_number = self.number
					row.tax_invoice_date = self.date
					row.supplier = self.party
					row.save(ignore_permissions=True)


	def compute_report_date(self):
		if int(self.months_delayed) == 0:
			self.db_set("report_date", self.date)
		else:
			self.db_set("report_date", add_months(self.date, int(self.months_delayed)))
