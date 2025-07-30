from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import ERP_CUSTOM_FIELDS

def execute():
    custom_fields = {
        "Account": list(filter(lambda l: l["fieldname"] in ["is_petty_cash_account"], ERP_CUSTOM_FIELDS["Account"]))
    }
    create_custom_fields(custom_fields, ignore_validate=True)
