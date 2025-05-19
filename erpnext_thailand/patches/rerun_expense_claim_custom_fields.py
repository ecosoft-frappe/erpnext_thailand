import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import HRMS_CUSTOM_FIELDS

def execute():
    if "hrms" in frappe.get_installed_apps():
        custom_fields = {
            "Expense Claim": HRMS_CUSTOM_FIELDS["Expense Claim"]
        }
        create_custom_fields(custom_fields, ignore_validate=True)
