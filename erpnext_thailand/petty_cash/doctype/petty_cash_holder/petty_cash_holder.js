// Copyright (c) 2025, Ecosoft and contributors
// For license information, please see license.txt

frappe.ui.form.on("Petty Cash Holder", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            if (!frm.doc.disabled) {
                // Top up to petty cash holder
                frm.add_custom_button(__("Top Up"), function() {
                    frappe.prompt([
                        {
                            label: "Posting Date",
                            fieldname: "posting_date",
                            fieldtype: "Date",
                            reqd: 1,
                            default: frappe.datetime.get_today(),
                        },
                        {
                            label: "Amount",
                            fieldname: "amount",
                            fieldtype: "Float",
                            precision: 2,
                            reqd: 1,
                            default: Math.max(frm.doc.petty_cash_float - frm.doc.petty_cash_balance, 0),
                        }
                    ], function(value) {
                        frappe.confirm(
                            `
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 150px;vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;border-top: 1px solid;"><b>Date</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;border-top: 1px solid;">${value.posting_date.split("-").reverse().join("-")}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;"><b>Petty Cash Holder</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;">${frm.doc.petty_cash_holder}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;"><b>From Account</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;">${frm.doc.cash_bank_account_for_petty_cash_top_up}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;"><b>To Account</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;">${frm.doc.petty_cash_account}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;border-bottom: 1px solid;"><b>Amount</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;border-bottom: 1px solid;">${Number(value.amount).toLocaleString(undefined, {minimumFractionDigits: 2,maximumFractionDigits: 2})}</td>
                                </tr>
                            </table>
                            <br>
                            Are you sure you want to confirm this transaction?`,
                            function() {
                                // Validate amount
                                if (value.amount <= 0) {
                                    frappe.throw(__("Amount must be positive value."));
                                }
                                // Create journal entry
                                frappe.call({
                                    method: "erpnext_thailand.petty_cash.doctype.petty_cash_holder.petty_cash_holder.create_journal_entry",
                                    args: {
                                        "posting_date": value.posting_date,
                                        "petty_cash_holder": frm.doc.name,
                                        "from_account": frm.doc.cash_bank_account_for_petty_cash_top_up,
                                        "to_account": frm.doc.petty_cash_account,
                                        "amount": value.amount,
                                        "type": "topup",
                                    },
                                    callback: function (r) {
                                        if (r.message) {
                                            frappe.msgprint({
                                                title: __("Success"),
                                                message: __(`The petty cash holder has received the top up successfully.<br><br>Journal Entry Reference: <a href="/app/journal-entry/` + r.message.name + `" target="_blank"><b>` + r.message.name + `</b></a>`),
                                                indicator: "green",
                                            });
                                            frm.reload_doc();
                                        }
                                    }
                                });
                            }
                        );
                    }, "Top Up");
                });
                // Withdraw from petty cash holder
                frm.add_custom_button(__("Withdraw"), function() {
                    frappe.prompt([
                        {
                            label: "Posting Date",
                            fieldname: "posting_date",
                            fieldtype: "Date",
                            reqd: 1,
                            default: frappe.datetime.get_today(),
                        },
                        {
                            label: "Amount",
                            fieldname: "amount",
                            fieldtype: "Float",
                            precision: 2,
                            reqd: 1,
                            default: 0,
                        }
                    ], function(value) {
                        frappe.confirm(
                            `
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 150px;vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;border-top: 1px solid;"><b>Date</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;border-top: 1px solid;">${value.posting_date.split("-").reverse().join("-")}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;"><b>Petty Cash Holder</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;">${frm.doc.petty_cash_holder}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;"><b>From Account</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;">${frm.doc.petty_cash_account}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;"><b>To Account</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;">${frm.doc.cash_bank_account_for_petty_cash_withdraw}</td>
                                </tr>
                                <tr>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-left: 1px solid;border-right: 1px solid;border-bottom: 1px solid;"><b>Amount</b></td>
                                    <td style="vertical-align:top;padding-left: 5px;padding-right: 5px;border-right: 1px solid;border-bottom: 1px solid;">${Number(value.amount).toLocaleString(undefined, {minimumFractionDigits: 2,maximumFractionDigits: 2})}</td>
                                </tr>
                            </table>
                            <br>
                            Are you sure you want to confirm this transaction?`,
                            function() {
                                // Validate amount
                                if (value.amount <= 0) {
                                    frappe.throw(__("Amount must be positive value."));
                                }
                                // Create journal entry
                                frappe.call({
                                    method: "erpnext_thailand.petty_cash.doctype.petty_cash_holder.petty_cash_holder.create_journal_entry",
                                    args: {
                                        "posting_date": value.posting_date,
                                        "petty_cash_holder": frm.doc.name,
                                        "from_account": frm.doc.petty_cash_account,
                                        "to_account": frm.doc.cash_bank_account_for_petty_cash_withdraw,
                                        "amount": value.amount,
                                        "type": "withdraw",
                                    },
                                    callback: function (r) {
                                        if (r.message) {
                                            frappe.msgprint({
                                                title: __("Success"),
                                                message: __(`The petty cash holder has completed the withdrawal successfully.<br><br>Journal Entry Reference: <a href="/app/journal-entry/` + r.message.name + `" target="_blank"><b>` + r.message.name + `</b></a>`),
                                                indicator: "green",
                                            });
                                            frm.reload_doc();
                                        }
                                    }
                                });
                            }
                        );
                    }, "Withdraw");
                });
            }
            // History
            frm.add_custom_button(__("History"), function() {
                frappe.set_route("List", "GL Entry", {petty_cash_holder: frm.doc.name});
            });
            // Enable, Disable
            if (!frm.doc.disabled) {
                frm.add_custom_button(__("Disable"), function() {
                    frm.set_value("disabled", 1);
                    frm.save();
                });
            } else {
                frm.add_custom_button(__("Enable"), function() {
                    frm.set_value("disabled", 0);
                    frm.save();
                });
            }
        }
    }
});
