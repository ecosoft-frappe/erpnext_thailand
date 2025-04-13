frappe.ui.form.on("Sales Order", {

    refresh: function(frm) {
        erpnext_thailand.deposit_utils.add_create_deposit_button(frm);    
    }

});