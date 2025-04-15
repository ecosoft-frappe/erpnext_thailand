frappe.provide("erpnext_thailand.deposit_utils");

erpnext_thailand.deposit_utils.get_deposits = function(frm, is_button_clicked = true) {
    frappe.call({
        method: "erpnext_thailand.custom.deposit_utils.get_deposits",
        args: { doc: frm.doc },
        callback: function(r) {
            // Clear existing deductions
            frm.clear_table("deposits");
            if (r.message.length > 0) {
                let deductions = r.message;
                let allocated_amount = 0;

                // Add new deductions
                deductions.forEach(function(d) {
                    let c = frm.add_child("deposits");
                    c.reference_name = d.reference_name;
                    c.reference_row = d.reference_row;
                    c.remarks = d.remarks;
                    c.deposit_amount = d.deposit_amount;
                    c.allocated_amount = d.allocated_amount;

                    // Keep track of the total allocated amount
                    allocated_amount += d.allocated_amount;
                });

                // Show alert only if not triggered by button click
                if (!is_button_clicked) {
                    let formatted_amount = new Intl.NumberFormat().format(allocated_amount);
                    frappe.show_alert({
                        message: __(
                            "Deposit amount <b>{0}</b> will be allocated.<br/>\
                            Please verify <b>Deposit Deductions</b> section in tab Payment.<br/>\
                            Then save the document to add the deduction amount in Items child table.",
                            [formatted_amount]
                        ),
                        indicator: "green"
                    }, 10);
                }
            }

            // Refresh the child table
            frm.refresh_field("deposits");
            frm.dirty();
        }
    });
};

erpnext_thailand.deposit_utils.add_create_deposit_button = function(frm) {
    // Add a custom button "Create Deposit Invoice"
    if (!frm.is_new() && frm.doc.docstatus === 1 && !frm.doc.deposit_invoice) {
        frm.add_custom_button(__("Create Deposit Invoice"), function() {
            // Open a dialog to ask for % deposit and amount deposit
            let is_updating = false; // Flag to prevent infinite loops

            const dialog = new frappe.ui.Dialog({
                title: __("Create Deposit Invoice"),
                fields: [
                    {
                        label: __("Deposit Percentage"),
                        fieldname: "deposit_percentage",
                        fieldtype: "Percent",
                        reqd: 1,
                        default: frm.doc.percent_deposit
                    },
                    {
                        label: __("Deposit Amount"),
                        fieldname: "deposit_amount",
                        fieldtype: "Currency",
                        reqd: 1,
                        default: (frm.doc.total || 0) * frm.doc.percent_deposit / 100
                    }
                ],
                primary_action_label: __("Create"),
                primary_action: function(values) {
                    if (!values.deposit_amount) {
                        frappe.msgprint({
                            title: __("Warning"),
                            indicator: "orange",
                            message: __("Deposit Percentage/Amount are required")
                        });
                        return;
                    }
                    // Use frappe.model.open_mapped_doc to create the Purchase Invoice
                    frappe.model.open_mapped_doc({
                        method: "erpnext_thailand.custom.deposit_utils.create_deposit_invoice",
                        frm: frm,
                        args: {
                            doctype: frm.doc.doctype,
                            deposit_amount: values.deposit_amount,
                        }
                    });
                    dialog.hide();
                }
            });

            // Add event listeners to update fields dynamically
            dialog.fields_dict.deposit_percentage.$input.on("input", function() {
                if (is_updating) return;
                is_updating = true;

                const percent = parseFloat(dialog.get_value("deposit_percentage") || 0);
                const total = frm.doc.total || 0;

                if (percent > 100) {
                    frappe.msgprint({
                        title: __("Warning"),
                        indicator: "orange",
                        message: __("Deposit Percentage cannot exceed 100%.")
                    });
                    dialog.set_value("deposit_percentage", 100);
                }

                const amount = (total * percent) / 100;
                dialog.set_value("deposit_amount", amount);
                is_updating = false;
            });

            dialog.fields_dict.deposit_amount.$input.on("input", function() {
                if (is_updating) return;
                is_updating = true;

                const amount = parseFloat(dialog.get_value("deposit_amount") || 0);
                const total = frm.doc.total || 0;
                const percent = total > 0 ? (amount / total) * 100 : 0;

                if (percent > 100) {
                    frappe.msgprint({
                        title: __("Warning"),
                        indicator: "orange",
                        message: __("Deposit Percentage cannot exceed 100%.")
                    });
                    dialog.set_value("deposit_percentage", 100);
                    dialog.set_value("deposit_amount", total);
                } else {
                    dialog.set_value("deposit_percentage", percent);
                }

                is_updating = false;
            });

            dialog.show();
        }).addClass(frm.doc.has_deposit ? "btn-primary" : "btn-secondary");;
    }
};