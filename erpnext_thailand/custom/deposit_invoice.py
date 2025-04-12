import frappe
from frappe import _
from frappe.utils import get_link_to_form


def get_invoice_order_type(doc):
    if doc.doctype == "Sales Invoice":
        return "Sales Order", "sales_order"
    elif doc.doctype == "Purchase Invoice":
        return "Purchase Order", "purchase_order"
    else:
        frappe.throw(_("Not an invoice document!"))


def validate_invoice(doc, methods):
    if doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
        frappe.throw(_("Not an invoice document!"))
    
    order_doctype, order_field = get_invoice_order_type(doc)

    if doc.is_deposit_invoice:
        validate_deposit_invoice(doc, order_doctype, order_field)
    else:
        validate_normal_invoice(doc, order_doctype, order_field)


def validate_deposit_invoice(doc, order_doctype, order_field):
    """
    Validation conditions
    1. Ensure only one line item and it is a deposit
    2. Validate link with SO/PO and amount
    3. Deposit invoice must be the first invoice being created for the same order
    If all the above constraints are passed, and it has docstatus 0 or 1, update deposit invoice back to SO/PO.
    """
    # Condition 1: Ensure only one line item and it is a deposit
    if len(doc.items) != 1 or not frappe.db.get_value("Item", doc.items[0].item_code, "is_deposit_item"):
        frappe.throw(_("Deposit invoice must contain only one deposit line item."))

    # Condition 2: Validate link with SO/PO and amount
    linked_doc = doc.items[0].get(order_field)
    if not linked_doc:
        frappe.throw(_("Deposit invoice must be linked to a {}.").format(order_doctype))
    linked_doc_amount = frappe.db.get_value(order_doctype, linked_doc, "grand_total")
    if doc.items[0].amount > linked_doc_amount:
        frappe.throw(_("Deposit invoice amount cannot exceed the {}'s amount.").format(order_doctype))

    # Condition 3: Deposit invoice must be the first invoice being created for the same order
    existing_invoices = frappe.get_all(
		doc.doctype,
		filters=[
			[doc.doctype, "name", "!=", doc.name],
			[doc.doctype, "docstatus", "<", 2],
			[f"{doc.doctype} Item", order_field, "=", linked_doc],
		],
		limit=1,
	)
    if existing_invoices:
        link = get_link_to_form(order_doctype, linked_doc)
        frappe.throw(_("Cannot create deposit invoice for order {}.<br/>Deposit invoice must be the 1st invoice").format(link))

    # Update deposit invoice back to SO/PO
    if doc.docstatus in [0, 1]:
        order = frappe.get_cached_doc(order_doctype, linked_doc)
        order.db_set("deposit_invoice", doc.name, update_modified=False)
        order.reload()


def validate_normal_invoice(doc, order_doctype, order_field):
    """ For normal invoice, if it's order require 1st deposit, ensure they are not the first invoice """
    linked_docs = {item.get(order_field) for item in doc.items if item.get(order_field)}
    for linked_doc in linked_docs:
        order = frappe.get_value(order_doctype, linked_doc, ["has_deposit", "deposit_invoice"], as_dict=True)
        # If the linked order must 1st invoice deposit, but it not yet has it.
        if order["has_deposit"] and not order["deposit_invoice"]:
            link = get_link_to_form(order_doctype, linked_doc)
            frappe.throw(_("The 1st invoice of {} should be a deposit invoice.").format(link))


def cancel_deposit_invoice(doc, method):
    if not doc.is_deposit_invoice:
        return
    order_doctype, order_field = get_invoice_order_type(doc)
    linked_doc = doc.items[0].get(order_field)
    order = frappe.get_cached_doc(order_doctype, linked_doc)
    order.db_set("deposit_invoice", "", update_modified=False)
    order.reload()
    # TODO: please make sure it is not cancelled if it already used as deposit deduction
