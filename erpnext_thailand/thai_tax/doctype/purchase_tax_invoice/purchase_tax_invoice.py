# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months

from erpnext_thailand.custom.custom_api import get_thai_tax_settings


class PurchaseTaxInvoice(Document):
	def submit(self):
		if self.against_voucher_type == "Payment Entry":
			frappe.db.set_value(
				"Payment Entry", self.against_voucher, "has_purchase_tax_invoice", 1
			)
		super().submit()

	def cancel(self):
		if self.against_voucher_type == "Payment Entry":
			frappe.db.set_value(
				"Payment Entry", self.against_voucher, "has_purchase_tax_invoice", 0
			)
		super().cancel()

	def validate(self):
		self.set_tax_id_branch_code()
		self.validate_account()
		self.compute_report_date()

	def before_update_after_submit(self):
		self.set_tax_id_branch_code()

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
				else:  # find in Purchase Invoice Detail Tax Invoice
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

	def set_tax_id_branch_code(self):
		"""Keep the supplier tax info at the time the tax invoice is issued"""
		if self.is_new() and self.tax_id:  # Given by the caller
			return
		if not self.is_new() and not self.has_value_changed("party"):
			return
		self.tax_id, self.branch_code = get_supplier_tax_id_branch_code(
			self.party, self.voucher_type, self.voucher_no
		)

	@frappe.whitelist()
	def get_refreshed_tax_id_branch_code(self):
		"""Tax ID and Branch Code from the address or supplier, for the Refresh button"""
		return get_supplier_tax_id_branch_code(self.party, self.voucher_type, self.voucher_no)

	def compute_report_date(self):
		if int(self.months_delayed) == 0:
			self.db_set("report_date", self.date)
		else:
			self.db_set("report_date", add_months(self.date, int(self.months_delayed)))

	def validate_account(self):
		"""Get purchase tax account from thai tax settings, make sure the account is correct"""
		setting = get_thai_tax_settings(self.company)
		if self.account != setting.purchase_tax_account:
			frappe.throw(
				_(
					"Tax Invoice creation failed,<br/>"
					"- Invalid account is being assigned to Tax Invoice<br/>"
					"- Returning Invoice with both negative rate and quantity is incorrect"
				)
			)


def get_supplier_tax_id_branch_code(supplier, voucher_type=None, voucher_no=None):
	"""Use Tax ID and Branch Code of the Purchase Invoice supplier address if it has Tax ID,
	otherwise use the ones of the supplier"""
	if voucher_type == "Purchase Invoice" and voucher_no:
		invoice = frappe.db.get_value(
			"Purchase Invoice", voucher_no, ["supplier", "supplier_address"], as_dict=True
		)
		if invoice and invoice.supplier == supplier and invoice.supplier_address:
			address = frappe.db.get_value(
				"Address", invoice.supplier_address, ["tax_id", "branch_code"], as_dict=True
			)
			if address and address.tax_id:
				return address.tax_id, address.branch_code or "00000"
	supplier = (
		frappe.db.get_value("Supplier", supplier, ["tax_id", "branch_code"], as_dict=True)
		or {}
	)
	return supplier.get("tax_id"), supplier.get("branch_code")
