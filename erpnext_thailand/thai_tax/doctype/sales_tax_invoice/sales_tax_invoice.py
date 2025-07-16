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

    def validate(self):
        self.validate_account()
        self.compute_report_date()
        self.compute_tax_percent()

    def on_update_after_submit(self):
        if self.get_doc_before_save():  # Some change is made
            self.compute_report_date()
            self.compute_tax_percent()

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
        """ Get sales tax account from thai tax settings, make sure the account is correct """
        setting = get_thai_tax_settings(self.company)
        if self.account != setting.sales_tax_account:
            frappe.throw(_(
                "Tax Invoice creation failed,<br/>"
                "- Invalid account is being assigned to Tax Invoice<br/>"
                "- Returning Invoice with both negative rate and quantity is incorrect"
            ))