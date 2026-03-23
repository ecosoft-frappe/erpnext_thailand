from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from erpnext_thailand.constants import HRMS_CUSTOM_FIELDS

def execute():
    custom_fields = {
        "Expense Claim": list(filter(lambda l: l["fieldname"] in ["is_petty_cash", "petty_cash_holder", "petty_cash_holder_name"], HRMS_CUSTOM_FIELDS["Expense Claim"]))
    }
    create_custom_fields(custom_fields, ignore_validate=True)
