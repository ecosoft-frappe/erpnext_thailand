frappe.provide("erpnext_thailand.etax");

const ETAX_METHOD = "erpnext_thailand.thai_etax.etax_service";
const SIGNED_STATUSES = ["Processing", "Success", "Replaced"];
const STATUS_COLORS = {
	Processing: "orange",
	Success: "green",
	Error: "red",
	Replaced: "blue",
};

erpnext_thailand.etax = {
	applies_to(frm) {
		if (frm.doctype === "Payment Entry") return "Payment Entry";
		if (frm.doc.is_return) return "Credit Note";
		if (frm.doc.is_debit_note) return "Debit Note";
		return "Sales Invoice";
	},

	// Document type code the purpose code must apply to
	purpose_document_type_code(frm) {
		if (frm.doctype === "Sales Invoice") {
			if (frm.doc.is_return) return "81";
			if (frm.doc.is_debit_note) return "80";
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
			),
		}));
		frm.get_field("etax_status").df.formatter = (value) =>
			erpnext_thailand.etax.status_indicator(value);
	},

	// Colored pill for e-Tax Status, shared by the form and the list view
	status_indicator(value, filterable) {
		if (!value) return "";
		const color = STATUS_COLORS[value] || "gray";
		// filterable: clicking the pill in the list view filters by this status
		const attrs = filterable
			? `class="indicator-pill ${color} ellipsis filterable"
				data-filter="etax_status,=,${frappe.utils.escape_html(value)}"`
			: `class="indicator-pill ${color} ellipsis"`;
		return `<span ${attrs}><span class="ellipsis">${__(value)}</span></span>`;
	},

	status_alerts: {
		Success: [__("Digitally signed e-Tax document"), STATUS_COLORS.Success],
		Processing: [__("e-Tax document is processing"), STATUS_COLORS.Processing],
		Replaced: [__("This e-Tax document has been replaced"), STATUS_COLORS.Replaced],
		Error: [__("e-Tax signing failed, see the e-Tax tab for details"), STATUS_COLORS.Error],
	},

	set_status_alert(frm) {
		const alert = erpnext_thailand.etax.status_alerts[frm.doc.etax_status];
		if (alert) {
			// permanent: the status alert has no close button
			frm.layout.show_message(alert[0], alert[1], true);
		}
	},

	needs_purpose(frm) {
		const is_adjustment =
			frm.doctype === "Sales Invoice" && (frm.doc.is_return || frm.doc.is_debit_note);
		return (
			(is_adjustment || frm.doc.amended_from) &&
			!((frm.doc.etax_purpose_code || "").trim() && (frm.doc.etax_purpose || "").trim())
		);
	},

	async refresh(frm) {
		const etax = erpnext_thailand.etax;
		etax.set_status_alert(frm);
		if (frm.doc.docstatus !== 1) return;
		if (
			frm.doctype === "Payment Entry" &&
			!(frm.doc.payment_type === "Receive" && frm.doc.party_type === "Customer")
		) {
			return;
		}
		const { message: enabled } = await frappe.call({
			method: `${ETAX_METHOD}.is_etax_enabled`,
			args: { company: frm.doc.company },
		});
		if (!enabled) return;

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
		// 380 (ใบแจ้งหนี้) is not a tax invoice and has no replacement
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
			args: { doctype: frm.doctype, name: frm.doc.name, ...args },
			freeze: true,
			freeze_message: __("Communicating with e-Tax server..."),
			callback: () => frm.reload_doc(),
		});
	},

	sign_dialog(frm) {
		// A replacement keeps the document type of the original
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
						filters: { applies_to: erpnext_thailand.etax.applies_to(frm) },
					}),
				},
			],
			primary_action_label: __("Sign"),
			primary_action(values) {
				dialog.hide();
				erpnext_thailand.etax.call(frm, "sign_etax", values);
			},
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
						),
					}),
					async onchange() {
						const code = dialog.get_value("etax_purpose_code");
						if (!code) return;
						const { message } = await frappe.db.get_value(
							"eTax Purpose Code",
							code,
							"reason"
						);
						dialog.set_value("etax_purpose", (message && message.reason) || "");
					},
				},
				{
					fieldname: "etax_purpose",
					fieldtype: "Data",
					label: __("Purpose"),
					reqd: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action(values) {
				frappe.confirm(
					__("{0} will be cancelled and a replacement will be created. Continue?", [
						frm.doc.name,
					]),
					() => {
						dialog.hide();
						frappe.call({
							method: `${ETAX_METHOD}.create_replacement`,
							args: { doctype: frm.doctype, name: frm.doc.name, ...values },
							freeze: true,
							callback: (r) =>
								r.message && frappe.set_route("Form", frm.doctype, r.message),
						});
					}
				);
			},
		});
		dialog.show();
	},
};

erpnext_thailand.etax.sign_list_dialog = function (listview) {
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
				get_query: () =>
					doctype === "Payment Entry"
						? { filters: { applies_to: "Payment Entry" } }
						: { filters: { applies_to: ["!=", "Payment Entry"] } },
			},
		],
		primary_action_label: __("Sign"),
		primary_action(values) {
			dialog.hide();
			frappe.call({
				method: `${ETAX_METHOD}.sign_etax_documents`,
				args: { doctype, names, ...values },
				freeze: true,
				freeze_message: __("Communicating with e-Tax server..."),
				callback: (r) => {
					const rows = Object.entries(r.message || {}).map(
						([name, result]) =>
							`<tr><td>${name}</td><td>${frappe.utils.escape_html(
								result || ""
							)}</td></tr>`
					);
					frappe.msgprint({
						title: __("e-Tax Result"),
						message: `<table class="table table-bordered">${rows.join("")}</table>`,
					});
					listview.refresh();
				},
			});
		},
	});
	dialog.show();
};

["Sales Invoice", "Payment Entry"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		setup: (frm) => erpnext_thailand.etax.setup(frm),
		refresh: (frm) => erpnext_thailand.etax.refresh(frm),
		// A new purpose code brings its default reason, the user may still edit it
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
			frm.set_value("etax_purpose", (message && message.reason) || "");
		},
	});
});
