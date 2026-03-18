import frappe

def execute():
    frappe.reload_doc("thai_tax", "doctype", "withholding_tax_type")
