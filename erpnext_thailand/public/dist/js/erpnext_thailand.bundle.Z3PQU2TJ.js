(() => {
  // ../erpnext_thailand/erpnext_thailand/public/js/print_format.js
  frappe.provide("erpnext_thailand.print");
  erpnext_thailand.print.print_pdf = function(doc) {
    frappe.call({
      method: "erpnext_thailand.custom.print_format.get_print_formats",
      args: {
        doctype: doc.doctype,
        docname: doc.name
      },
      callback: function(r) {
        if (r.message) {
          let { print_formats, default_format, default_copies } = r.message;
          let d = new frappe.ui.Dialog({
            title: __("Select Print Format"),
            fields: [
              {
                label: __("Print Format"),
                fieldname: "print_format",
                fieldtype: "Select",
                options: print_formats,
                reqd: 1,
                default: default_format
              }
            ],
            primary_action_label: __("Print PDF"),
            primary_action(values) {
              let print_format = values.print_format;
              const w = window.open(
                "/api/method/erpnext_thailand.custom.print_format.download_print_pdf?doctype=" + encodeURIComponent(doc.doctype) + "&name=" + encodeURIComponent(doc.name) + "&format=" + encodeURIComponent(print_format)
              );
              if (!w) {
                frappe.msgprint(__("Please enable pop-ups"));
              }
              d.hide();
            }
          });
          d.show();
        }
      }
    });
  };

  // ../erpnext_thailand/erpnext_thailand/public/js/deposit_utils.js
  frappe.provide("erpnext_thailand.deposit_utils");
  erpnext_thailand.deposit_utils.get_deposits = function(frm, is_button_clicked = true) {
    frappe.call({
      method: "erpnext_thailand.custom.deposit_utils.get_deposits",
      args: { doc: frm.doc },
      callback: function(r) {
        frm.clear_table("deposits");
        if (r.message.length > 0) {
          let deductions = r.message;
          let allocated_amount = 0;
          deductions.forEach(function(d) {
            let c = frm.add_child("deposits");
            c.reference_name = d.reference_name;
            c.reference_row = d.reference_row;
            c.remarks = d.remarks;
            c.deposit_amount = d.deposit_amount;
            c.allocated_amount = d.allocated_amount;
            allocated_amount += d.allocated_amount;
          });
          if (!is_button_clicked) {
            let formatted_amount = new Intl.NumberFormat().format(allocated_amount);
            frappe.show_alert({
              message: __(
                "Deposit amount <b>{0}</b> will be allocated when you save this invoice.",
                [formatted_amount]
              ),
              indicator: "green"
            }, 10);
          }
        }
        frm.refresh_field("deposits");
        frm.dirty();
      }
    });
  };
  erpnext_thailand.deposit_utils.add_create_deposit_button = function(frm) {
    if (!frm.is_new() && frm.doc.docstatus === 1 && !frm.doc.deposit_invoice) {
      frm.add_custom_button(__("Create Deposit Invoice"), function() {
        let is_updating = false;
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
            frappe.model.open_mapped_doc({
              method: "erpnext_thailand.custom.deposit_utils.create_deposit_invoice",
              frm,
              args: {
                doctype: frm.doc.doctype,
                deposit_amount: values.deposit_amount
              }
            });
            dialog.hide();
          }
        });
        dialog.fields_dict.deposit_percentage.$input.on("input", function() {
          if (is_updating)
            return;
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
          const amount = total * percent / 100;
          dialog.set_value("deposit_amount", amount);
          is_updating = false;
        });
        dialog.fields_dict.deposit_amount.$input.on("input", function() {
          if (is_updating)
            return;
          is_updating = true;
          const amount = parseFloat(dialog.get_value("deposit_amount") || 0);
          const total = frm.doc.total || 0;
          const percent = total > 0 ? amount / total * 100 : 0;
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
      }).addClass(frm.doc.has_deposit ? "btn-primary" : "btn-secondary");
      ;
    }
  };
  erpnext_thailand.deposit_utils.get_deposit_item = function(frm) {
    if (frm.doc.is_deposit_invoice) {
      frm.doc.items = [];
      frappe.call({
        method: "erpnext_thailand.custom.item.get_deposit_item",
        args: {
          company: frm.doc.company
        },
        callback: function(r) {
          if (r.message) {
            cost_center = frm.doc.doctype == "Sales Invoice" ? r.message.selling_cost_center : r.message.buying_cost_center;
            frm.set_value("cost_center", cost_center);
            frm.add_child("items", {
              item_code: r.message.item_code,
              item_name: r.message.item_name,
              uom: r.message.uom,
              qty: 1,
              is_deposit_item: 1,
              income_account: r.message.sales_deposit_account,
              expense_account: r.message.purchase_deposit_account
            });
            frm.refresh_field("items");
          } else {
            frappe.msgprint(__("No deposit items found!"));
          }
        }
      });
    } else {
      frm.doc.items = frm.doc.items.filter((item) => item.is_deposit_item !== 1);
      frm.refresh_field("items");
    }
  };
})();
//# sourceMappingURL=erpnext_thailand.bundle.Z3PQU2TJ.js.map
