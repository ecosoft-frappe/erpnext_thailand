frappe.ui.form.on("Purchase Tax Invoice", {
	refresh(frm) {
		frm.set_query("company_tax_address", function () {
			return {
				filters: {
					is_your_company_address: true,
				},
			};
		});
		if (!frm.is_new() && frm.doc.docstatus < 2 && frm.perm[0].write) {
			frm.add_custom_button(__("Refresh Tax ID / Branch Code"), function () {
				frm.events.refresh_tax_id_branch_code(frm);
			});
		}
	},

	refresh_tax_id_branch_code(frm) {
		frm.call("get_refreshed_tax_id_branch_code").then((r) => {
			const [tax_id, branch_code] = r.message || [];
			if (
				(tax_id || "") === (frm.doc.tax_id || "") &&
				(branch_code || "") === (frm.doc.branch_code || "")
			) {
				frappe.show_alert({
					message: __("Tax ID and Branch Code are already up to date"),
					indicator: "blue",
				});
				return;
			}
			// Tax ID and Branch Code may be edited by hand, confirm before overwriting them
			frappe.confirm(
				__(
					"Change Tax ID from {0} to {1} and Branch Code from {2} to {3}?",
					[frm.doc.tax_id, tax_id, frm.doc.branch_code, branch_code].map((value) =>
						frappe.utils.escape_html(value || "-")
					)
				),
				async () => {
					await frm.set_value({ tax_id: tax_id, branch_code: branch_code });
					frm.save(frm.doc.docstatus === 1 ? "Update" : "Save");
				}
			);
		});
	},
});
