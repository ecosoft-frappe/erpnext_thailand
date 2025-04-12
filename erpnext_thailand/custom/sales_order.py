import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def create_deposit_invoice(sales_order, deposit_percentage=None, deposit_amount=None):
    # Fetch the Sales Order
    so = frappe.get_doc("Sales Order", sales_order)

    # Fetch the deposit item
    deposit_item = frappe.call("erpnext_thailand.custom.item.get_deposit_item", company=so.company)
    if not deposit_item:
        frappe.throw(_("No deposit item or account is configured for the selected company."))

    # Calculate the deposit amount
    total_amount = so.grand_total or 0
    if deposit_amount:
        deposit_amount = float(deposit_amount)
    elif deposit_percentage:
        deposit_percentage = float(deposit_percentage)
        deposit_amount = (total_amount * deposit_percentage) / 100
    else:
        frappe.throw(_("Either deposit percentage or deposit amount must be provided."))

    # Create a new Sales Invoice (not saved)
    si = frappe.new_doc("Sales Invoice")
    si.customer = so.customer
    si.company = so.company
    si.due_date = frappe.utils.nowdate()
    si.is_deposit_invoice = 1
    si.currency = so.currency
    si.selling_price_list = so.selling_price_list
    si.append("items", {
        "item_code": deposit_item["item_code"],
        "item_name": deposit_item["item_name"],
        "qty": 1,
        "rate": deposit_amount,
        "income_account": deposit_item["sales_deposit_account"],
        "uom": deposit_item["uom"],
        "sales_order": so.name,
        "cost_center": frappe.db.get_value("Company", so.company, "cost_center")
    })

    # Return the document as a dictionary (not saved)
    return si.as_dict()