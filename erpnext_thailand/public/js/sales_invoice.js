frappe.ui.form.on("Sales Invoice", {
    before_load: function(frm) {
        if (frm.doc.__islocal && frm.doc.amended_from) {
            frm.set_value("tax_invoice_number", "");
            frm.set_value("tax_invoice_date", "");
        }
    },

    onload: function(frm) {
        // Delay for 1 second and then trigger get_deposits
        if (frm.is_new() && !frm.doc.is_deposit_invoice) {
            setTimeout(function() {
                frm.events.get_deposits(frm, false);
            }, 1000)    
        };
    },

    get_deposits(frm, is_button_clicked = true) {
        frappe.call({
            method: "erpnext_thailand.custom.deposit_invoice.get_deposits",
            args: { doc: frm.doc },
            callback: function(r) {
                if (r.message.length > 0) {
                    let deductions = r.message;
                    let allocated_amount = 0;
                    // Clear existing deductions
                    frm.clear_table("deposits");
                    // Add new deductions
                    deductions.forEach(function(d) {
                        let c = frm.add_child("deposits");
                        c.reference_type = d.reference_type
                        c.reference_name = d.reference_name
                        c.reference_row = d.reference_row
                        c.remarks = d.remarks
                        c.deposit_amount = d.deposit_amount
                        c.allocated_amount = d.allocated_amount
                        // Keep track of the total allocated amount
                        allocated_amount += d.allocated_amount
                    });
                    
                    // Refresh the child table
                    frm.refresh_field("deposits");
                    if (!is_button_clicked) {
                        let formatted_amount = new Intl.NumberFormat().format(allocated_amount);
                        frappe.show_alert({
                            message: __(
                                "Deposit amount <b>{0}</b> will be allocated.<br/>\
                                Please verify Deposit Deductions section in tab Payment.<br/>\
                                Then save the document to add the deduction amount in Items child table.",
                                [formatted_amount]),
                            indicator: "green"
                        }, 20);
                    }
                }
            }
        });
    }
});
