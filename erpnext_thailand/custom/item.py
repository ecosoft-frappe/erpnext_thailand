import frappe
from frappe import _

def validate_deposit_item(doc, method):
    if doc.is_stock_item:
        doc.is_deposit_item = 0
    if doc.is_deposit_item:
        if not doc.deposit_accounts:
            frappe.throw(_("Please set Deposit Account for Deposit Item"))