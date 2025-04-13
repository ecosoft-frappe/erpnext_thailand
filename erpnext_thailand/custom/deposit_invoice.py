import json
import frappe
from frappe import _
from frappe.utils import get_link_to_form
from frappe.model.mapper import get_mapped_doc


def get_invoice_order_type(doctype):
    if doctype == "Sales Invoice":
        return "Sales Order", "sales_order"
    elif doctype == "Purchase Invoice":
        return "Purchase Order", "purchase_order"
    else:
        frappe.throw(_("Not an invoice document!"))


def validate_invoice(doc, methods):
    if doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
        frappe.throw(_("Not an invoice document!"))
    
    order_doctype, order_field = get_invoice_order_type(doc.doctype)

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
    """ 
    1. For normal invoice, if it's order require 1st deposit, ensure they are not the first invoice 
    2. Allocation amount must not exceed the deposit amount.
    """
    # Ensure this is not the first invoice in case of require deposit
    linked_docs = {item.get(order_field) for item in doc.items if item.get(order_field)}
    for linked_doc in linked_docs:
        order = frappe.get_value(order_doctype, linked_doc, ["has_deposit", "deposit_invoice"], as_dict=True)
        # If the linked order must 1st invoice deposit, but it not yet has it.
        if order["has_deposit"] and not order["deposit_invoice"]:
            link = get_link_to_form(order_doctype, linked_doc)
            frappe.throw(_("The 1st invoice of {} should be a deposit invoice.").format(link))

    # Ensure allocation amount must not exceed the deposit amount
    for d in doc.deposits:
        if d.allocated_amount > d.deposit_amount:
            frappe.throw(_("Allocated amount cannot exceed the deposit amount."))


def cancel_deposit_invoice(doc, method):
    if not doc.is_deposit_invoice:
        return
    order_doctype, order_field = get_invoice_order_type(doc.doctype)
    linked_doc = doc.items[0].get(order_field)
    order = frappe.get_cached_doc(order_doctype, linked_doc)
    order.db_set("deposit_invoice", "", update_modified=False)
    order.reload()
    # TODO: please make sure it is not cancelled if it already used as deposit deduction


def apply_deposit_deduction(doc, method):
    """
    If the row of deductions child table in this invoice has allocation_amount
    Get the Sales Invoice Item from row.reference_row
    Copy data in the Sales Invoice Item as another row in this invoice with rate = negative allocation_amount
    """
    if doc.is_deposit_invoice or doc.docstatus != 0:  # Only draft
        return

    # Remove any line item with is_deposit_item = 1
    doc.items = [item for item in doc.items if not frappe.db.get_value("Item", item.item_code, "is_deposit_item")]
    next_idx = len(doc.items)
    for d in doc.deposits:
        if d.allocated_amount and d.reference_row:
            # Fetch the Sales Invoice Item using reference_row
            reference_item = frappe.get_doc(f"{doc.doctype} Item", d.reference_row)
            # Copy the reference item and modify necessary fields
            new_item = reference_item.as_dict()
            next_idx += 1
            new_item.update({
                "idx": next_idx,
                "name": None,  # Clear the name to allow insertion as a new row
                "parent": doc.name,
                "parentfield": "items",
                "parenttype": doc.doctype,
                "qty": 1,
                "rate": -d.allocated_amount,
                "amount": -d.allocated_amount,
            })
            doc.append("items", new_item)


@frappe.whitelist()
def create_deposit_invoice(source_name, target_doc=None):
    """
    Create a deposit Invoice from an Order.
    This method is used with frappe.model.open_mapped_doc.
    """

    order_doctype = frappe.flags.args.doctype
    doctype_field = "sales_order" if order_doctype == "Sales Order" else "purchase_order"
    invoice_doctype = "Sales Invoice" if order_doctype == "Sales Order" else "Purchase Invoice"
    deposit_account_field = "sales_deposit_account" if order_doctype == "Sales Order" else "purchase_deposit_account"
    account_field = "income_account" if order_doctype == "Sales Order" else "expense_account"

    def set_missing_values(source, target):
        # Set additional fields on the target document
        target.is_deposit_invoice = 1
        target.due_date = frappe.utils.nowdate()

        # Add the deposit item
        deposit_item = frappe.call(
            "erpnext_thailand.custom.item.get_deposit_item", company=source.company
        )
        if not deposit_item:
            frappe.throw(_("No deposit item is configured for the company {0}.").format(source.company))

        target.append("items", {
            "item_code": deposit_item["item_code"],
            "item_name": deposit_item["item_name"],
            "qty": 1,
            "rate": frappe.flags.args.deposit_amount,
            account_field: deposit_item[deposit_account_field],
            "uom": deposit_item["uom"],
            doctype_field: source.name,
            "cost_center": frappe.db.get_value("Company", source.company, "cost_center")
        })

    # Map the Order to a Invoice
    doc = get_mapped_doc(
        order_doctype,
        source_name,
        {
            order_doctype: {
                "doctype": invoice_doctype,
                "validation": {"docstatus": ["=", 1]}
            }
        },
        target_doc,
        set_missing_values
    )

    return doc


@frappe.whitelist()
def get_deposits(doc):
    invoice = json.loads(doc)
    invoice_doctype = invoice["doctype"]
    order_doctype, order_field = get_invoice_order_type(invoice_doctype)
    # From the invoice, loop through items and we can get all order.
    orders = {item.get(order_field) for item in invoice.get("items", []) if item.get(order_field)}
    deductions = []
    for order in orders:
        # Get all deposit invoices linked to the sales order
        deposit_invoices = frappe.get_all(
            invoice_doctype,
            filters={
                "docstatus": 1,
                "is_deposit_invoice": 1,
                order_field: order
            },
            pluck="name"
        )
        for di in deposit_invoices:
            di = frappe.get_cached_doc(invoice_doctype, di)
            if not di.items:
                continue

            initial_amount = di.items[0].amount
            # Get the total allocated amount from the deductions line with same reference_row
            prev_deducts = frappe.get_all(
                invoice_doctype,
                filters=[
                    [invoice_doctype, "docstatus", "=", 1],
                    [invoice_doctype, "is_deposit_invoice", "=", 0],
                    [f"{invoice_doctype} Deposit", "reference_row", "=", di.items[0].name],
                ],
                fields=["name", f"`tab{invoice_doctype} Deposit`.allocated_amount"],
            )
            deducted_amount = sum(d["allocated_amount"] for d in prev_deducts)
            # Remaining Deposit
            balance = initial_amount - deducted_amount
            # Allocation must not exceed amount of the same order
            invoice_amount = sum([
                item.get("amount")
                for item in invoice.get("items", [])
                if item.get(order_field) == order and not item.get("is_deposit_item")
            ])
            allocated_amount = min(invoice_amount, balance)
            if allocated_amount <= 0:
                continue
            deductions.append({
                "reference_name": di.name,
                "reference_row": di.items[0].name,
                "remarks": di.items[0].description,
                "deposit_amount": balance,
                "allocated_amount": allocated_amount,
            })

    return deductions