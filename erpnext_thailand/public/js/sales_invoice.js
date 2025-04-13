frappe.ui.form.on("Sales Invoice", {
    before_load: function(frm) {
        if (frm.doc.__islocal && frm.doc.amended_from) {
            frm.set_value("tax_invoice_number", "");
            frm.set_value("tax_invoice_date", "");
        }
    },

    refresh: function(frm) {
        // Delay for 1 second and then trigger get_deposits
        if (frm.is_new() && !frm.doc.is_deposit_invoice) {
            setTimeout(function() {
                frm.events.get_deposits(frm, false);
            }, 1000)    
        };
    },

    get_deposits: function(frm, is_button_clicked = true) {
        erpnext_thailand.deposit_utils.get_deposits(frm, is_button_clicked);
    }
});
