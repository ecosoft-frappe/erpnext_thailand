// Copyright (c) 2024, Ecosoft and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Billing", {

    refresh(frm) {
        frm.fields_dict["purchase_billing_line"].grid.get_field("purchase_invoice").get_query = function(doc, cdt, cdn) {            
            return {
                filters: {
                    'supplier': ["=", doc.supplier],
                    'docstatus': 1
                }
            }
        }
    },

    // Add Multiple Button
    onload_post_render: function(frm) {
		frm.get_field("purchase_billing_line").grid.set_multiple_add("purchase_invoice");
	},

	get_purchase_invoices(frm) {        
        if (frm.doc.threshold_date) {
            return frm.call({
                method: "erpnext_thailand.thai_billing.doctype.purchase_billing.purchase_billing.get_due_billing",
                args: {
                    supplier: frm.doc.supplier,
                    currency: frm.doc.currency,
					tax_type: frm.doc.tax_type,
                    threshold_type: frm.doc.threshold_type,
                    threshold_date: frm.doc.threshold_date
                },
                callback: function(r) {
                    let invoices = []
                    for (let i of r.message) {
                        invoices.push({
                            purchase_invoice: i.name,
                            invoice_date: i.posting_date,
                            due_date: i.due_date,
                            reference: i.po_no,
                            outstanding_amount: i.outstanding_amount,
                            grand_total: i.grand_total,
                            payment_term: i.payment_terms_template,
                        });
                    }
                    frm.set_value("purchase_billing_line", invoices)
                    frm.set_value("invoice_count", invoices.length)
                    frm.refresh_field('purchase_billing_line');
                }
            });
        }
    }
})

frappe.ui.form.on("Purchase Billing Line", {

    purchase_billing_line_add(frm, cdt, cdn) {
        frm.set_value("invoice_count", frm.doc.invoice_count + 1)
    },
    purchase_billing_line_remove(frm, cdt, cdn) {
        frm.set_value("invoice_count", frm.doc.invoice_count - 1)
    }

})