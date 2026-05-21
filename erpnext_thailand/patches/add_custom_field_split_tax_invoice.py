
from frappe.custom.doctype.custom_field.custom_field import \
    create_custom_fields

from erpnext_thailand.constants import ERP_CUSTOM_FIELDS


def execute():
    custom_fields = {
        "Journal Entry": list(filter(lambda l: l["fieldname"] in ["section_break_split_tax_invoice", "split_tax_invoice", "splitted_tax_invoices", "section_break_pxm0e", "tax_invoice_details"], ERP_CUSTOM_FIELDS["Journal Entry"]))
    }
    create_custom_fields(custom_fields, ignore_validate=True)
