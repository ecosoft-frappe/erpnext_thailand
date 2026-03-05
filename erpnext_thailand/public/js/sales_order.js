frappe.ui.form.on("Sales Order", {
    refresh: frm => erpnext_thailand.deposit_utils.add_create_deposit_button(frm),

    deposit_amount: frm => {
        let { total, deposit_amount } = frm.doc;
        if (total && deposit_amount != null)
            frm.set_value("percent_deposit", deposit_amount / total * 100);
    },

    percent_deposit: frm => {
        let { total, percent_deposit } = frm.doc;
        if (total && percent_deposit != null)
            frm.set_value("deposit_amount", total * percent_deposit / 100);
    }
});