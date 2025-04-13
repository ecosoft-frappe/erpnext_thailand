import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def create_deposit_invoice(source_name, target_doc=None):
    """
    Create a deposit Sales Invoice from a Sales Order.
    This method is used with frappe.model.open_mapped_doc.
    """
    from frappe.model.mapper import get_mapped_doc

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
            "income_account": deposit_item["sales_deposit_account"],
            "uom": deposit_item["uom"],
            "sales_order": source.name,
            "cost_center": frappe.db.get_value("Company", source.company, "cost_center")
        })

    # Map the Sales Order to a Sales Invoice
    doc = get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Sales Invoice",
                "validation": {"docstatus": ["=", 1]}
            }
        },
        target_doc,
        set_missing_values
    )

    return doc