import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import DEPOSIT_CUSTOM_FIELDS

def execute():
    frappe.db.delete("Custom Field", {"fieldname": "has_deposit", "dt": ["in", ["Sales Order", "Purchase Order"]]})
    custom_fields = {
        "Sales Order": list(filter(lambda l: l["fieldname"] in ["has_deposit"], DEPOSIT_CUSTOM_FIELDS["Sales Order"])),
        "Purchase Order": list(filter(lambda l: l["fieldname"] in ["has_deposit"], DEPOSIT_CUSTOM_FIELDS["Purchase Order"]))
    }
    create_custom_fields(custom_fields, ignore_validate=True)
