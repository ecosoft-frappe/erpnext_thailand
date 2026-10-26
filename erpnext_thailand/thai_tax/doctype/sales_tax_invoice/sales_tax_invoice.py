import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months

from erpnext_thailand.custom.custom_api import get_thai_tax_settings


class SalesTaxInvoice(Document):
	def autoname(self):
		setting = get_thai_tax_settings(self.company)
		if setting.use_doc_name_for_sales_taxinv:
			self.name = self.voucher_no
		# When manual mode is enabled, use tax_invoice_number as the document name (zero tax only)
		elif (
			setting.create_sales_taxinv_on_zero_tax
			and setting.get("manual_keyin_sales_taxinv_on_zero_tax")
			and self.tax_amount == 0
		):
			voucher = frappe.get_doc(self.voucher_type, self.voucher_no)
			if voucher.tax_invoice_number:
				self.name = voucher.tax_invoice_number

	def validate(self):
		self.set_tax_id_branch_code()
		self.validate_account()
		self.compute_report_date()
		self.compute_tax_percent()

	def before_update_after_submit(self):
		# In case party is customized to allow on submit
		self.set_tax_id_branch_code()

	def on_update_after_submit(self):
		if self.get_doc_before_save():  # Some change is made
			self.compute_report_date()
			self.compute_tax_percent()

	def set_tax_id_branch_code(self):
		"""Keep the customer tax info at the time the tax invoice is issued"""
		if self.is_new() and self.tax_id:  # Given by the caller
			return
		if not self.is_new() and not self.has_value_changed("party"):
			return
		self.tax_id, self.branch_code = get_customer_tax_id_branch_code(
			self.party, self.voucher_type, self.voucher_no
		)

	@frappe.whitelist()
	def get_refreshed_tax_id_branch_code(self):
		"""Tax ID and Branch Code from the address or customer, for the Refresh button"""
		return get_customer_tax_id_branch_code(self.party, self.voucher_type, self.voucher_no)

	def compute_report_date(self):
		if int(self.months_delayed) == 0:
			self.db_set("report_date", self.date)
		else:
			self.db_set("report_date", add_months(self.date, int(self.months_delayed)))

	def compute_tax_percent(self):
		if self.tax_base:
			self.db_set("tax_percent", round((self.tax_amount / self.tax_base * 100), 0))
		else:
			self.db_set("tax_percent", 0)

	def validate_account(self):
		"""Get sales tax account from thai tax settings, make sure the account is correct"""
		setting = get_thai_tax_settings(self.company)
		if self.account != setting.sales_tax_account:
			frappe.throw(
				_(
					"Tax Invoice creation failed,<br/>"
					"- Invalid account is being assigned to Tax Invoice<br/>"
					"- Returning Invoice with both negative rate and quantity is incorrect"
				)
			)


def get_customer_tax_id_branch_code(customer, voucher_type=None, voucher_no=None):
	"""Use Tax ID and Branch Code of the Sales Invoice customer address if it has Tax ID,
	otherwise use the ones of the customer"""
	if voucher_type == "Sales Invoice" and voucher_no:
		invoice = frappe.db.get_value(
			"Sales Invoice", voucher_no, ["customer", "customer_address"], as_dict=True
		)
		if invoice and invoice.customer == customer and invoice.customer_address:
			address = frappe.db.get_value(
				"Address", invoice.customer_address, ["tax_id", "branch_code"], as_dict=True
			)
			if address and address.tax_id:
				return address.tax_id, address.branch_code or "00000"
	customer = (
		frappe.db.get_value("Customer", customer, ["tax_id", "branch_code"], as_dict=True)
		or {}
	)
	return customer.get("tax_id"), customer.get("branch_code")
