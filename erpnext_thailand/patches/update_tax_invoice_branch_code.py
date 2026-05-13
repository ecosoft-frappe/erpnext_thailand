import frappe


def get_branch_code(doctype, voucher_no, party):
    if doctype == "Sales Tax Invoice" and voucher_no:
        addr = frappe.db.get_value("Sales Invoice", voucher_no, "customer_address")
        if addr:
            branch_code = frappe.db.get_value("Address", addr, "branch_code")
            if branch_code:
                return branch_code
        if party:
            return frappe.db.get_value("Customer", party, "branch_code")

    if doctype == "Purchase Tax Invoice" and voucher_no:
        addr = frappe.db.get_value("Purchase Invoice", voucher_no, "supplier_address")
        if addr:
            branch_code = frappe.db.get_value("Address", addr, "branch_code")
            if branch_code:
                return branch_code
        if party:
            return frappe.db.get_value("Supplier", party, "branch_code")

    return None

def backfill_branch_code(doctype):
    docs = frappe.get_all(
        doctype,
        filters={"docstatus": ["!=", 2]},
        fields=["name", "voucher_no", "party", "branch_code"],
    )
    for d in docs:
        if d.branch_code:
            continue
        branch_code = get_branch_code(doctype, d.voucher_no, d.party)
        if branch_code:
            frappe.db.set_value(doctype, d.name, "branch_code", branch_code)

def execute():
    frappe.reload_doc("thai_tax", "doctype", "sales_tax_invoice")
    frappe.reload_doc("thai_tax", "doctype", "purchase_tax_invoice")

    backfill_branch_code("Sales Tax Invoice")
    backfill_branch_code("Purchase Tax Invoice")