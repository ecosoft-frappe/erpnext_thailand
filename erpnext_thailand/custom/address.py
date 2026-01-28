import frappe

def update_tax_info_in_linked_doc(doc, method):
    if doc.update_tax_branch:
        linked_docs = doc.links
        did_update = False

        for link in linked_docs:
            if link.link_doctype in ["Customer", "Supplier"]:
                frappe.db.set_value(link.link_doctype, link.link_name, {
                    "tax_id": doc.tax_id,
                    "branch_code": doc.branch_code
                })
                did_update = True
        
        if did_update:
            frappe.msgprint("Tax ID and Branch Code updated in linked Customer/Supplier.", alert=True, indicator="green")