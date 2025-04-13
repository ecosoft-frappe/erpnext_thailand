frappe.ui.form.on("Purchase Order", {

    refresh: function(frm) {
        erpnext_thailand.deposit_utils.add_create_deposit_button(frm);
    }

});