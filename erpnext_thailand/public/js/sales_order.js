frappe.ui.form.on("Sales Order", {
    refresh: function(frm) {
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
                            default: 10
                        },
                        {
                            label: __("Deposit Amount"),
                            fieldname: "deposit_amount",
                            fieldtype: "Currency",
                            reqd: 1,
                            default: (frm.doc.grand_total || 0) * 0.1
                        }
                    ],
                    primary_action_label: __("Create"),
                    primary_action: function(values) {
                        dialog.hide();

                        // Call server-side function to create the Sales Invoice
                        frappe.call({
                            method: "erpnext_thailand.custom.sales_order.create_deposit_invoice",
                            args: {
                                sales_order: frm.doc.name,
                                deposit_percentage: values.deposit_percentage
                            },
                            callback: function(response) {
                                if (response.message) {
                                    // Open the new Sales Invoice in draft mode
                                    frappe.model.with_doctype("Sales Invoice", function() {
                                        const si = frappe.model.sync(response.message)[0];
                                        frappe.set_route("Form", "Sales Invoice", si.name);
                                    });
                                }
                            }
                        });
                    }
                });

                // Add event listeners to update fields dynamically
                dialog.fields_dict.deposit_percentage.$input.on("input", function() {
                    if (is_updating) return;
                    is_updating = true;

                    const percent = parseFloat(dialog.get_value("deposit_percentage") || 0);
                    const total = frm.doc.grand_total || 0;

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
                    const total = frm.doc.grand_total || 0;
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
    }
});