frappe.listview_settings["Payment Entry"] = frappe.listview_settings["Payment Entry"] || {};
const payment_entry_listview = frappe.listview_settings["Payment Entry"];

payment_entry_listview.formatters = {
	...(payment_entry_listview.formatters || {}),
	wht_status(value) {
		if (!value) return "";
		const color = value === "Issued" ? "green" : "gray";
		return `<span class="indicator-pill ${color} filterable ellipsis"
			data-filter="wht_status,=,${value}">
			<span class="ellipsis">${__(value)}</span></span>`;
	},
};

const payment_entry_onload = payment_entry_listview.onload;
payment_entry_listview.onload = function (listview) {
	payment_entry_onload && payment_entry_onload(listview);
	// Report View also calls onload, but its columns are datatable columns
	if (listview.view_name !== "List") return;

	// Show WHT Status right after Status, so it is not cut off by the column limit
	const setup_columns = listview.setup_columns.bind(listview);
	listview.setup_columns = function () {
		setup_columns();
		if (this.list_view_settings && this.list_view_settings.fields) return;
		const df = frappe.meta.get_docfield(this.doctype, "wht_status");
		if (!df) return;

		const index = this.columns.findIndex((col) => col.df && col.df.fieldname === "wht_status");
		if (index > -1) {
			this.columns.splice(index, 1);
		} else {
			// Keep the column count, drop the last field column
			const last = this.columns.findLastIndex(
				(col) => col.type === "Field" && col.df.fieldname !== "name"
			);
			if (last > -1) this.columns.splice(last, 1);
		}
		const status = this.columns.findIndex((col) => col.type === "Status");
		const position = status > -1 ? status + 1 : 2;
		this.columns.splice(position, 0, { type: "Field", df });
	};
	listview.setup_columns();
	listview.render_header(true);
};
