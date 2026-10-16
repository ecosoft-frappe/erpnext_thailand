(() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };

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
            frappe.show_alert(
              {
                message: __(
                  "Deposit amount <b>{0}</b> will be allocated when you save this invoice.",
                  [formatted_amount]
                ),
                indicator: "green"
              },
              10
            );
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

  // ../erpnext_thailand/erpnext_thailand/public/js/etax.js
  frappe.provide("erpnext_thailand.etax");
  var ETAX_METHOD = "erpnext_thailand.thai_etax.etax_service";
  var SIGNED_STATUSES = ["Processing", "Success", "Replaced"];
  var STATUS_COLORS = {
    Processing: "orange",
    Success: "green",
    Error: "red",
    Replaced: "blue"
  };
  erpnext_thailand.etax = {
    applies_to(frm) {
      if (frm.doctype === "Payment Entry")
        return "Payment Entry";
      if (frm.doc.is_return)
        return "Credit Note";
      if (frm.doc.is_debit_note)
        return "Debit Note";
      return "Sales Invoice";
    },
    purpose_document_type_code(frm) {
      if (frm.doctype === "Sales Invoice") {
        if (frm.doc.is_return)
          return "81";
        if (frm.doc.is_debit_note)
          return "80";
      }
      return frm.doc.etax_document_type_code;
    },
    purpose_code_filters(code) {
      return code ? [["eTax Purpose Code Applicable", "document_type_code", "=", code]] : [];
    },
    setup(frm) {
      frm.set_query("etax_purpose_code", () => ({
        filters: erpnext_thailand.etax.purpose_code_filters(
          erpnext_thailand.etax.purpose_document_type_code(frm)
        )
      }));
      frm.get_field("etax_status").df.formatter = (value) => erpnext_thailand.etax.status_indicator(value);
    },
    status_indicator(value, filterable) {
      if (!value)
        return "";
      const color = STATUS_COLORS[value] || "gray";
      const attrs = filterable ? `class="indicator-pill ${color} ellipsis filterable"
				data-filter="etax_status,=,${frappe.utils.escape_html(value)}"` : `class="indicator-pill ${color} ellipsis"`;
      return `<span ${attrs}><span class="ellipsis">${__(value)}</span></span>`;
    },
    status_alerts: {
      Success: [__("Digitally signed e-Tax document"), STATUS_COLORS.Success],
      Processing: [__("e-Tax document is processing"), STATUS_COLORS.Processing],
      Replaced: [__("This e-Tax document has been replaced"), STATUS_COLORS.Replaced],
      Error: [__("e-Tax signing failed, see the e-Tax tab for details"), STATUS_COLORS.Error]
    },
    set_status_alert(frm) {
      const alert = erpnext_thailand.etax.status_alerts[frm.doc.etax_status];
      if (alert) {
        frm.layout.show_message(alert[0], alert[1], true);
      }
    },
    needs_purpose(frm) {
      const is_adjustment = frm.doctype === "Sales Invoice" && (frm.doc.is_return || frm.doc.is_debit_note);
      return (is_adjustment || frm.doc.amended_from) && !((frm.doc.etax_purpose_code || "").trim() && (frm.doc.etax_purpose || "").trim());
    },
    async refresh(frm) {
      const etax = erpnext_thailand.etax;
      etax.set_status_alert(frm);
      if (frm.doc.docstatus !== 1)
        return;
      if (frm.doctype === "Payment Entry" && !(frm.doc.payment_type === "Receive" && frm.doc.party_type === "Customer")) {
        return;
      }
      const { message: enabled } = await frappe.call({
        method: `${ETAX_METHOD}.is_etax_enabled`,
        args: { company: frm.doc.company }
      });
      if (!enabled)
        return;
      const status = frm.doc.etax_status;
      if (!SIGNED_STATUSES.includes(status)) {
        if (frm.doctype === "Sales Invoice" && etax.needs_purpose(frm)) {
          frm.dashboard.set_headline_alert(
            __(
              "To send this credit/debit note as e-Tax, select an e-Tax Purpose Code and enter its purpose in the e-Tax tab, then Update."
            ),
            "blue"
          );
        } else {
          frm.add_custom_button(__("Sign e-Tax"), () => etax.sign_dialog(frm), __("e-Tax"));
        }
      }
      if (status === "Processing") {
        frm.add_custom_button(
          __("Refresh e-Tax Status"),
          () => etax.call(frm, "refresh_etax_status"),
          __("e-Tax")
        );
      }
      if (status === "Success" && frm.doc.etax_document_type_code !== "380") {
        frm.add_custom_button(
          __("Create Replacement"),
          () => etax.replacement_dialog(frm),
          __("e-Tax")
        );
      }
    },
    call(frm, method, args = {}) {
      return frappe.call({
        method: `${ETAX_METHOD}.${method}`,
        args: __spreadValues({ doctype: frm.doctype, name: frm.doc.name }, args),
        freeze: true,
        freeze_message: __("Communicating with e-Tax server..."),
        callback: () => frm.reload_doc()
      });
    },
    sign_dialog(frm) {
      const locked = Boolean(frm.doc.amended_from && frm.doc.etax_document_type);
      const dialog = new frappe.ui.Dialog({
        title: __("Sign e-Tax"),
        fields: [
          {
            fieldname: "etax_document_type",
            fieldtype: "Link",
            label: __("e-Tax Document Type"),
            options: "eTax Document Type",
            only_select: 1,
            reqd: 1,
            default: frm.doc.etax_document_type,
            read_only: locked,
            get_query: () => ({
              filters: { applies_to: erpnext_thailand.etax.applies_to(frm) }
            })
          }
        ],
        primary_action_label: __("Sign"),
        primary_action(values) {
          dialog.hide();
          erpnext_thailand.etax.call(frm, "sign_etax", values);
        }
      });
      dialog.show();
    },
    replacement_dialog(frm) {
      const dialog = new frappe.ui.Dialog({
        title: __("Create Replacement"),
        fields: [
          {
            fieldname: "etax_purpose_code",
            fieldtype: "Link",
            label: __("Purpose Code"),
            options: "eTax Purpose Code",
            reqd: 1,
            get_query: () => ({
              filters: erpnext_thailand.etax.purpose_code_filters(
                frm.doc.etax_document_type_code
              )
            }),
            async onchange() {
              const code = dialog.get_value("etax_purpose_code");
              if (!code)
                return;
              const { message } = await frappe.db.get_value(
                "eTax Purpose Code",
                code,
                "reason"
              );
              dialog.set_value("etax_purpose", message && message.reason || "");
            }
          },
          {
            fieldname: "etax_purpose",
            fieldtype: "Data",
            label: __("Purpose"),
            reqd: 1
          }
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
          frappe.confirm(
            __("{0} will be cancelled and a replacement will be created. Continue?", [
              frm.doc.name
            ]),
            () => {
              dialog.hide();
              frappe.call({
                method: `${ETAX_METHOD}.create_replacement`,
                args: __spreadValues({ doctype: frm.doctype, name: frm.doc.name }, values),
                freeze: true,
                callback: (r) => r.message && frappe.set_route("Form", frm.doctype, r.message)
              });
            }
          );
        }
      });
      dialog.show();
    }
  };
  erpnext_thailand.etax.sign_list_dialog = function(listview) {
    const names = listview.get_checked_items(true);
    if (!names.length) {
      frappe.msgprint(__("Please select documents to sign e-Tax"));
      return;
    }
    const doctype = listview.doctype;
    const dialog = new frappe.ui.Dialog({
      title: __("Sign e-Tax"),
      fields: [
        {
          fieldname: "etax_document_type",
          fieldtype: "Link",
          label: __("e-Tax Document Type"),
          options: "eTax Document Type",
          only_select: 1,
          reqd: 1,
          get_query: () => doctype === "Payment Entry" ? { filters: { applies_to: "Payment Entry" } } : { filters: { applies_to: ["!=", "Payment Entry"] } }
        }
      ],
      primary_action_label: __("Sign"),
      primary_action(values) {
        dialog.hide();
        frappe.call({
          method: `${ETAX_METHOD}.sign_etax_documents`,
          args: __spreadValues({ doctype, names }, values),
          freeze: true,
          freeze_message: __("Communicating with e-Tax server..."),
          callback: (r) => {
            const rows = Object.entries(r.message || {}).map(
              ([name, result]) => `<tr><td>${name}</td><td>${frappe.utils.escape_html(
                result || ""
              )}</td></tr>`
            );
            frappe.msgprint({
              title: __("e-Tax Result"),
              message: `<table class="table table-bordered">${rows.join("")}</table>`
            });
            listview.refresh();
          }
        });
      }
    });
    dialog.show();
  };
  ["Sales Invoice", "Payment Entry"].forEach((doctype) => {
    frappe.ui.form.on(doctype, {
      setup: (frm) => erpnext_thailand.etax.setup(frm),
      refresh: (frm) => erpnext_thailand.etax.refresh(frm),
      async etax_purpose_code(frm) {
        if (!frm.doc.etax_purpose_code) {
          frm.set_value("etax_purpose", "");
          return;
        }
        const { message } = await frappe.db.get_value(
          "eTax Purpose Code",
          frm.doc.etax_purpose_code,
          "reason"
        );
        frm.set_value("etax_purpose", message && message.reason || "");
      }
    });
  });
})();
//# sourceMappingURL=erpnext_thailand.bundle.FXWJJEIB.js.map
