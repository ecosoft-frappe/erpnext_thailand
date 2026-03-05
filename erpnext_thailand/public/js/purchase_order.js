frappe.ui.form.on("Purchase Tax Invoice", {
    refresh(frm) {
        frm.set_query("company_tax_address", () => ({
            filters: { is_your_company_address: true }
        }));
    },

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