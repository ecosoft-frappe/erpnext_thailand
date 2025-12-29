ERP_CUSTOM_FIELDS = {
	"Address": [
		{
			"fieldname": "tax_id",
			"fieldtype": "Data",
			"label": "Tax ID",
			"insert_after": "disabled"
		},
		{
			"fieldname": "branch_code",
			"fieldtype": "Data",
			"label": "Branch Code",
			"insert_after": "tax_id"
		},
		{
			"fieldname": "update_tax_branch",
			"fieldtype": "Check",
			"label": "Update Tax ID/Branch Code",
			"insert_after": "branch_code",
			"description": "Update Tax ID and Brach Code to linked Customer/Supplier"
		},
  
	],
	"Print Format": [
		{
			"fieldname": "default_condition",
			"fieldtype": "Data",
			"label": "Default Condition",
			"description": "Use python expression to set default format, i.e., doc.doctype=='Sales Invoice'",
			"insert_after": "disabled"
		},
		{
			"fieldname": "hide_if_not_default",
			"fieldtype": "Check",
			"label": "Hide if not Default",
			"description": "If default condition is not met, hide this format form selection",
			"insert_after": "default_condition"
		},
		{
			"fieldname": "add_comment_info",
			"fieldtype": "Check",
			"label": "Add Comment",
			"description": "Add printed as comment in document activity",
			"insert_after": "hide_if_not_default"
		},
		{
			"fieldname": "add_copies",
			"fieldtype": "Select",
			"label": "Additional Copies",
			"options": "\n1\n2\n3\n4",
			"description": "2 additional copies will print 3 copies, 1 original and 2 copies. For jinja template, doc.copy = 0 is original, else copies.",
			"insert_after": "add_comment_info",
		}
	],
	"Payment Entry": [
		{
			"depends_on": "eval:doc.payment_type=='Pay'",
			"fieldname": "has_purchase_tax_invoice",
			"fieldtype": "Check",
			"insert_after": "payment_order_status",
			"label": "Has Purchase Tax Invoice",
		},
		{
			"fieldname": "tax_invoice",
			"fieldtype": "Tab Break",
			"insert_after": "title",
			"label": "Tax Invoice",
		},
		{
			"fieldname": "company_tax_address",
			"fieldtype": "Link",
			"insert_after": "tax_invoice",
			"label": "Company Tax Address",
			"options": "Address",
		},
		{
			"fieldname": "column_break_bqyze",
			"fieldtype": "Column Break",
			"insert_after": "company_tax_address",
		},
		{
			"fieldname": "tax_base_amount",
			"fieldtype": "Float",
			"insert_after": "column_break_bqyze",
			"label": "Tax Base Amount",
		},
		{
			"fieldname": "section_break_owjbn",
			"fieldtype": "Section Break",
			"insert_after": "tax_base_amount",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_number",
			"fieldtype": "Data",
			"in_standard_filter": 1,
			"insert_after": "section_break_owjbn",
			"label": "Tax Invoice Number",
			"no_copy": 1,
			"read_only_depends_on": "eval:doc.docstatus!=0",
		},
		{
			"allow_on_submit": 1,
			"depends_on": "eval:doc.party_type=='Employee'",
			"fieldname": "supplier",
			"fieldtype": "Link",
			"insert_after": "tax_invoice_number",
			"label": "Supplier",
			"no_copy": 1,
			"options": "Supplier",
		},
		{
			"fieldname": "column_break_yio5c",
			"fieldtype": "Column Break",
			"insert_after": "supplier",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_date",
			"fieldtype": "Date",
			"insert_after": "column_break_yio5c",
			"label": "Tax Invoice Date",
			"no_copy": 1,
			"read_only_depends_on": "eval:doc.docstatus!=0",
		},
		{
			"allow_on_submit": 1,
			"depends_on": "eval:doc.party_type=='Employee'",
			"fetch_from": "supplier.supplier_name",
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"insert_after": "tax_invoice_date",
			"label": "Supplier Name",
			"no_copy": 1,
			"translatable": 1,
		},
	],
	"Payment Entry Deduction": [
		{
			"fieldname": "section_break_s4fwa",
			"fieldtype": "Section Break",
			"insert_after": "description",
		},
		{
			"fieldname": "withholding_tax_type",
			"fieldtype": "Link",
			"insert_after": "section_break_s4fwa",
			"label": "Withholding Tax Type",
			"options": "Withholding Tax Type",
		},
		{
			"fieldname": "column_break_lx8hk",
			"fieldtype": "Column Break",
			"insert_after": "withholding_tax_type",
		},
		{
			"fieldname": "withholding_tax_base",
			"fieldtype": "Float",
			"insert_after": "column_break_lx8hk",
			"label": "Withholding Tax Base",
		},
	],
	"Supplier": [
		{
			"default": "00000",
			"fieldname": "branch_code",
			"fieldtype": "Data",
			"insert_after": "tax_id",
			"label": "Branch Code",
		}
	],
	"Customer": [
		{
			"default": "00000",
			"fieldname": "branch_code",
			"fieldtype": "Data",
			"insert_after": "tax_id",
			"label": "Branch Code",
		},
	],
	"Journal Entry": [
		{
			"fieldname": "tax_invoice",
			"fieldtype": "Tab Break",
			"insert_after": "auto_repeat",
			"label": "Tax Invoice",
			"depends_on": "eval:doc.create_tax_invoice==1",
		},
		{
			"fieldname": "company_tax_address",
			"fieldtype": "Link",
			"insert_after": "tax_invoice",
			"label": "Company Tax Address",
			"options": "Address",
		},
		{
			"fieldname": "create_tax_invoice",
			"fieldtype": "Check",
			"insert_after": "voucher_type",
			"label": "Create Tax Invoice",
			"description": "If checked, system will create Tax Invoice record for tax entry",
		},
		{
			"fieldname": "column_break_3djv9",
			"fieldtype": "Column Break",
			"insert_after": "company_tax_address",
		},
		{
			"fieldname": "for_payment",
			"fieldtype": "Link",
			"insert_after": "column_break_3djv9",
			"label": "For Payment",
			"options": "Payment Entry",
		},
		{
			"fieldname": "section_break_pxm0e",
			"fieldtype": "Section Break",
			"insert_after": "for_payment",
		},
		{
			"fieldname": "tax_invoice_details",
			"fieldtype": "Table",
			"insert_after": "section_break_pxm0e",
			"label": "Tax Invoice Details",
			"no_copy": 1,
			"options": "Journal Entry Tax Invoice Detail",
		},
	],
	"Sales Invoice": [
		{
			"fieldname": "tax_invoice",
			"fieldtype": "Tab Break",
			"insert_after": "total_billing_amount",
			"label": "Tax Invoice",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_number",
			"fieldtype": "Data",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"insert_after": "tax_invoice",
			"label": "Tax Invoice Number",
			"no_copy": 1,
		},
		{
			"fieldname": "column_break_cijbv",
			"fieldtype": "Column Break",
			"insert_after": "tax_invoice_number",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_date",
			"fieldtype": "Date",
			"insert_after": "column_break_cijbv",
			"label": "Tax Invoice Date",
			"no_copy": 1,
		},
	],
	"Sales Invoice Item": [
		{
			"description": "Default Withholding Tax Type setup on Item",
			"fetch_from": "item_code.withholding_tax_type",
			"fetch_if_empty": 1,
			"fieldname": "withholding_tax_type",
			"fieldtype": "Link",
			"insert_after": "item_tax_template",
			"label": "Withholding Tax Type",
			"options": "Withholding Tax Type",
			"print_hide": 1,
			"read_only": 1,
		},
	],
	"Purchase Invoice": [
		{
			"fieldname": "tax_invoice",
			"fieldtype": "Tab Break",
			"insert_after": "supplied_items",
			"label": "Tax Invoice",
		},
		{
			"fieldname": "section_break_split_tax_invoice",
			"fieldtype": "Section Break",
			"insert_after": "tax_invoice",
   			"label": ""
		},
		{
			"fieldname": "split_tax_invoice",
			"fieldtype": "Check",
			"insert_after": "section_break_split_tax_invoice",
			"label": "Split Tax Invoices",
			"no_copy": 1,
		},
		{
			"fieldname": "splitted_tax_invoices",
			"fieldtype": "Table",
			"insert_after": "split_tax_invoice",
			"label": "Splitted Tax Invoices",
			"options": "Purchase Invoice Tax Invoice Detail",
			"depends_on": "eval:doc.split_tax_invoice",
		},
		{
			"fieldname": "section_break_tax_invoice",
			"fieldtype": "Section Break",
			"insert_after": "splitted_tax_invoices",
   			"label": ""
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_number",
			"fieldtype": "Data",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"insert_after": "section_break_tax_invoice",
			"label": "Tax Invoice Number",
			"no_copy": 1,
			"read_only_depends_on": "eval:doc.docstatus!=0",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"fieldname": "column_break_t0qgt",
			"fieldtype": "Column Break",
			"insert_after": "tax_invoice_number",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_date",
			"fieldtype": "Date",
			"insert_after": "column_break_t0qgt",
			"label": "Tax Invoice Date",
			"no_copy": 1,
			"read_only_depends_on": "eval:doc.docstatus!=0",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
	],
 	"Purchase Invoice Item": [
		{
			"description": "Default Withholding Tax Type setup on Item",
			"fetch_from": "item_code.withholding_tax_type",
			"fetch_if_empty": 1,
			"fieldname": "withholding_tax_type",
			"fieldtype": "Link",
			"insert_after": "item_tax_template",
			"label": "Withholding Tax Type",
			"options": "Withholding Tax Type",
			"print_hide": 1,
			"read_only": 1,
		},
	],
	"Item": [
		{
			"fieldname": "section_break_6buh1",
			"fieldtype": "Section Break",
			"insert_after": "item_tax_section_break",
   			"label": "Thai Tax"
		},
		{
			"description": "Select withholding tax type for service amount withheld when recevice from customer.",
			"fieldname": "withholding_tax_type",
			"fieldtype": "Link",
			"insert_after": "section_break_6buh1",
			"label": "Withholding Tax Type (Customer)",
			"options": "Withholding Tax Type",
		},
		{
			"fieldname": "column_break_lhwzh",
			"fieldtype": "Column Break",
			"insert_after": "withholding_tax_type",
		},
		{
			"description": "Select withholding tax type for service amount to be withheld when pay to supplier.",
			"fieldname": "withholding_tax_type_pay_supplier",
			"fieldtype": "Link",
			"insert_after": "column_break_lhwzh",
			"label": "Withholding Tax Type (Supplier)",
			"options": "Withholding Tax Type",
		},
		{
			"description": "Select withholding tax type for service amount to be withheld when pay to individual.",
			"fieldname": "withholding_tax_type_pay_individual",
			"fieldtype": "Link",
			"insert_after": "withholding_tax_type_pay_supplier",
			"label": "Withholding Tax Type (Individual)",
			"options": "Withholding Tax Type",
		},
	],
	"Journal Entry Account": [
		{
			"collapsible": 1,
			"depends_on": "eval:doc.account_type == 'Tax'",
			"fieldname": "overwrite_tax_invoice",
			"fieldtype": "Section Break",
			"insert_after": "credit",
			"label": "Overwrite Tax Invoice",
		},
		{
			"fieldname": "tax_invoice_number",
			"fieldtype": "Data",
			"insert_after": "overwrite_tax_invoice",
			"label": "Tax Invoice Number",
		},
		{
			"fieldname": "tax_invoice_date",
			"fieldtype": "Date",
			"insert_after": "tax_invoice_number",
			"label": "Tax Invoice Date",
		},
		{
			"fieldname": "column_break_cun7x",
			"fieldtype": "Column Break",
			"insert_after": "tax_invoice_date",
		},
		{
			"fieldname": "supplier",
			"fieldtype": "Link",
			"insert_after": "column_break_cun7x",
			"label": "Supplier",
			"options": "Supplier",
		},
		{
			"fieldname": "customer",
			"fieldtype": "Link",
			"insert_after": "supplier",
			"label": "Customer",
			"options": "Customer",
		},
		{
			"description": "Leave this value to 0 and system will auto calculate based on tax rate.",
			"fieldname": "tax_base_amount",
			"fieldtype": "Float",
			"insert_after": "customer",
			"label": "Tax Base Amount",
		},
	],
    "Currency Exchange Settings": [
		{
			"depends_on": "eval:doc.service_provider == 'Bank of Thailand';",
			"fieldname": "token",
			"fieldtype": "Password",
			"insert_after": "access_key",
			"label": "Token",
			"mandatory_depends_on": "eval:doc.service_provider == 'Bank of Thailand';",
			"module": "Thai Tax"
		},
	]
}

HRMS_CUSTOM_FIELDS = {
	"Expense Claim": [
		{
			"fieldname": "tax_invoice",
			"fieldtype": "Tab Break",
			"insert_after": "total_amount_reimbursed",
			"label": "Tax Invoice",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "company_tax_address",
			"fieldtype": "Link",
			"insert_after": "tax_invoice",
			"label": "Company Tax Address",
			"options": "Address",
		},
		{
			"fieldname": "column_break_rqacr",
			"fieldtype": "Column Break",
			"insert_after": "company_tax_address",
		},
		{
			"description": "Use this field only when you want to overwrite",
			"fieldname": "base_amount_overwrite",
			"fieldtype": "Currency",
            "insert_after": "column_break_rqacr",
			"label": "Base Amount Overwrite",
			"no_copy": 1,
			"options": "Company:company:default_currency",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"fieldname": "section_break_split_tax_invoice",
			"fieldtype": "Section Break",
			"insert_after": "base_amount_overwrite",
   			"label": ""
		},
		{
			"fieldname": "split_tax_invoice",
			"fieldtype": "Check",
			"insert_after": "section_break_split_tax_invoice",
			"label": "Split Tax Invoices",
			"no_copy": 1,
		},
		{
			"fieldname": "splitted_tax_invoices",
			"fieldtype": "Table",
			"insert_after": "split_tax_invoice",
			"label": "Splitted Tax Invoices",
			"options": "Expense Claim Tax Invoice Detail",
			"depends_on": "eval:doc.split_tax_invoice",
		},
		{
			"fieldname": "section_break_uodhb",
			"fieldtype": "Section Break",
			"insert_after": "splitted_tax_invoices",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_number",
			"fieldtype": "Data",
			"in_standard_filter": 1,
			"insert_after": "section_break_uodhb",
			"label": "Tax Invoice Number",
			"read_only_depends_on": "eval:doc.docstatus!=0",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "supplier",
			"fieldtype": "Link",
			"insert_after": "tax_invoice_number",
			"label": "Supplier",
			"no_copy": 1,
			"options": "Supplier",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"fieldname": "column_break_6atpw",
			"fieldtype": "Column Break",
			"insert_after": "supplier",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"allow_on_submit": 1,
			"fieldname": "tax_invoice_date",
			"fieldtype": "Date",
			"insert_after": "column_break_6atpw",
			"label": "Tax Invoice Date",
			"no_copy": 1,
			"read_only_depends_on": "eval:doc.docstatus!=0",
			"depends_on": "eval:!doc.split_tax_invoice",
		},
		{
			"allow_on_submit": 1,
			"fetch_from": "supplier.supplier_name",
			"fieldname": "supplier_name",
			"fieldtype": "Data",
			"insert_after": "tax_invoice_date",
			"label": "Supplier Name",
			"no_copy": 1,
			"depends_on": "eval:!doc.split_tax_invoice",
		},
	],
}

ERP_PROPERTY_SETTERS = {
	"Purchase Taxes and Charges": [
		("rate", "precision", "6", "Select"),
	],
	"Sales Taxes and Charges": [
		("rate", "precision", "6", "Select"),
	],
	"Advance Taxes and Charges": [
		("rate", "precision", "6", "Select"),
	],
	"Sales Invoice": [
		("naming_series", "depends_on", "eval:!doc.amended_from", "Data"),
	],
	"Purchase Invoice": [
		("naming_series", "depends_on", "eval:!doc.amended_from", "Data"),
	],
	"Document Naming Settings": [
		("help_html", "options", "<div class=\"well\">\n    Edit list of Series in the box. Rules:\n    <ul>\n        <li>Each Series Prefix on a new line.</li>\n        <li>Allowed special characters are \"/\" and \"-\"</li>\n        <li>\n            Optionally, set the number of digits in the series using dot (.)\n            followed by hashes (#). For example, \".####\" means that the series\n            will have four digits. Default is five digits.\n        </li>\n        <li>\n            You can also use variables in the series name by putting them\n            between (.) dots\n            <br>\n            Supported Variables:\n            <ul>\n                <li><code>.YYYY.</code> - Year in 4 digits</li>\n                <li><code>.YYYY-DATE.</code> - Year in 4 digits by Document Date</li>\n                <li><code>.YY.</code> - Year in 2 digits</li>\n                <li><code>.YY-DATE.</code> - Year in 2 digits by Document Date</li>\n                <li><code>.MM.</code> - Month</li>\n                <li><code>.MM-DATE.</code> - Month by Document Date</li>\n                <li><code>.DD.</code> - Day of month</li>\n                <li><code>.DD-DATE.</code> - Day of month by Document Date</li>\n                <li><code>.WW.</code> - Week of the year</li>\n                <li><code>.WW-DATE.</code> - Week of the year by Document Date</li>\n                <li><code>.FY.</code> - Fiscal Year</li>\n                <li>\n                    <code>.{fieldname}.</code> - fieldname on the document e.g.\n                    <code>branch</code>\n                </li>\n            </ul>\n        </li>\n    </ul>\n    Examples:\n    <ul>\n        <li>INV-</li>\n        <li>INV-10-</li>\n        <li>INVK-</li>\n        <li>INV-.YYYY.-.{branch}.-.MM.-.####</li>\n    </ul>\n</div>\n<br>\n", "Text"),
	],
	"Currency Exchange Settings": [
		("service_provider", "options", "frankfurter.dev\nexchangerate.host\nBank of Thailand\nCustom", "Select"),
	],
}

BILLING_CUSTOM_FIELDS =  {
    "Payment Entry": [
        {
            "depends_on": 'eval:doc.docstatus == 0 && doc.payment_type == "Receive" && doc.party_type == "Customer" && doc.party',
            "fieldname": "get_invoices_from_sales_billing",
            "fieldtype": "Button",
            "insert_after": "get_outstanding_invoices",
            "label": "Get Invoices from Sales Billing",
        },
        {
            "depends_on": 'eval:doc.docstatus == 0 && doc.payment_type == "Receive" && doc.party_type == "Customer" && doc.party',
            "fieldname": "sales_billing",
            "read_only": 1,
            "fieldtype": "Link",
            "insert_after": "get_invoices_from_sales_billing",
            "label": "Sales Billing",
            "options": "Sales Billing",
        },
        {
            "depends_on": 'eval:doc.docstatus == 0 && doc.payment_type == "Pay" && doc.party_type == "Supplier" && doc.party',
            "fieldname": "get_invoices_from_purchase_billing",
            "fieldtype": "Button",
            "insert_after": "sales_billing",
            "label": "Get Invoices from Purchase Billing",
        },
        {
            "depends_on": 'eval:doc.docstatus == 0 && doc.payment_type == "Pay" && doc.party_type == "Supplier" && doc.party',
            "fieldname": "purchase_billing",
            "fieldtype": "Link",
            "read_only": 1,
            "insert_after": "get_invoices_from_purchase_billing",
            "label": "Purchase Billing",
            "options": "Purchase Billing",
        }
    ],
}

DEPOSIT_CUSTOM_FIELDS =  {
    "Item": [
		{
			"depends_on": "eval:!doc.is_stock_item",
			"fieldname": "is_deposit_item",
			"fieldtype": "Check",
			"insert_after": "is_stock_item",
			"label": "Is Deposit Item"
		},
	],
    "Sales Order": [
		{
			"fieldname": "section_break_o8q38",
			"fieldtype": "Section Break",
			"insert_after": "payment_schedule",
            "label": "Deposit",
		}, 
		{
			"description": "If checked, the 1st invoice from this order should be a deposit invoice.",
			"fieldname": "has_deposit",
			"fieldtype": "Check",
			"insert_after": "section_break_o8q38",
			"label": "Deposit on 1st Invoice",
			"allow_on_submit": 1
		},
		{
			"fieldname": "deposit_invoice",
			"fieldtype": "Data",
			"insert_after": "has_deposit",
			"label": "Deposit Invoice",
			"no_copy": 1,
			"read_only": 1
		},
		{
			"fieldname": "column_break_euapx",
			"fieldtype": "Column Break",
			"insert_after": "deposit_invoice"
		},
		{
			"fieldname": "percent_deposit",
			"fieldtype": "Percent",
			"insert_after": "column_break_euapx",
			"label": "Percent Deposit",
		},
		{
			"fieldname": "deposit_deduction_method",
			"fieldtype": "Select",
			"label": "Deposit Deduction Method",
			"options": "Percent\nFull Amount",
			"description": "Deposit deduction (return of deposit) on following invoice(s).",
			"insert_after": "percent_deposit",
		}
	],
    "Purchase Order": [
		{
			"fieldname": "section_break_o8q38",
			"fieldtype": "Section Break",
			"insert_after": "payment_schedule",
            "label": "Deposit",
		}, 
		{
			"description": "If checked, the 1st invoice from this order should be a deposit invoice.",
			"fieldname": "has_deposit",
			"fieldtype": "Check",
			"insert_after": "section_break_o8q38",
			"label": "Deposit on 1st Invoice",
			"allow_on_submit": 1
		},
		{
			"fieldname": "deposit_invoice",
			"fieldtype": "Data",
			"insert_after": "has_deposit",
			"label": "Deposit Invoice",
			"no_copy": 1,
			"read_only": 1
		},
		{
			"fieldname": "column_break_euapx",
			"fieldtype": "Column Break",
			"insert_after": "deposit_invoice"
		},
		{
			"fieldname": "percent_deposit",
			"fieldtype": "Percent",
			"insert_after": "column_break_euapx",
			"label": "Percent Deposit",
		},
		{
			"fieldname": "deposit_deduction_method",
			"fieldtype": "Select",
			"label": "Deposit Deduction Method",
			"options": "Percent\nFull Amount",
			"description": "Deposit deduction (return of deposit) on following invoice(s).",
			"insert_after": "percent_deposit",
		}
	],
    "Sales Invoice": [
		{
			"depends_on": "",
			"fieldname": "is_deposit_invoice",
			"fieldtype": "Check",
			"insert_after": "company_tax_id",
			"label": "Is Deposit Invoice",
			"read_only": 0
		},
		{
			"collapsible": 1,
			"collapsible_depends_on": "deposits",
			"depends_on": "eval:!doc.is_deposit_invoice",
			"fieldname": "deposit_deductions",
			"fieldtype": "Section Break",
			"insert_after": "advances",
			"label": "Deposit Deductions"
		},
		{
			"fieldname": "use_untied_deposit",
			"fieldtype": "Check",
			"insert_after": "deposit_deductions",
			"label": "Include Untied Deposits",
			"description": "Untied Deposits are deposits that are not linked to any order.",
		},
		{
			"fieldname": "manual_deposit_allocation",
			"fieldtype": "Check",
			"insert_after": "use_untied_deposit",
			"label": "Manual Deposit Allocation",
			"read_only": 0,
			"description": "Allow user to manually allowcate deposit amount to deduct.",
		},
		{
			"fieldname": "deposits",
			"fieldtype": "Table",
			"insert_after": "manual_deposit_allocation",
			"label": "Deposits",
			"options": "Sales Invoice Deposit",
			"read_only_depends_on": "eval:!doc.manual_deposit_allocation",
		}
	],
    "Sales Invoice Item": [
		{
			"fetch_from": "item_code.is_deposit_item",
			"fieldname": "is_deposit_item",
			"fieldtype": "Check",
			"insert_after": "item_code",
			"label": "Is Deposit Item",
			"read_only": 1
		},
	],
    "Purchase Invoice": [
		{
			"depends_on": "",
			"fieldname": "is_deposit_invoice",
			"fieldtype": "Check",
			"insert_after": "company",
			"label": "Is Deposit Invoice",
			"read_only": 0
		},
		{
			"collapsible": 1,
			"collapsible_depends_on": "deposits",
			"depends_on": "eval:!doc.is_deposit_invoice",
			"fieldname": "deposit_deductions",
			"fieldtype": "Section Break",
			"insert_after": "advance_tax",
			"label": "Deposit Deductions"
		},
		{
			"fieldname": "use_untied_deposit",
			"fieldtype": "Check",
			"insert_after": "deposit_deductions",
			"label": "Include Untied Deposits",
			"description": "Untied Deposits are deposits that are not linked to any order.",
		},
		{
			"fieldname": "manual_deposit_allocation",
			"fieldtype": "Check",
			"insert_after": "use_untied_deposit",
			"label": "Manual Deposit Allocation",
			"read_only": 0,
			"description": "Allow user to manually allowcate deposit amount to deduct.",
		},
		{
			"fieldname": "deposits",
			"fieldtype": "Table",
			"insert_after": "manual_deposit_allocation",
			"label": "Deposits",
			"options": "Purchase Invoice Deposit",
			"read_only_depends_on": "eval:!doc.manual_deposit_allocation",
		}
	],
    "Purchase Invoice Item": [
		{
			"fetch_from": "item_code.is_deposit_item",
			"fieldname": "is_deposit_item",
			"fieldtype": "Check",
			"insert_after": "item_code",
			"label": "Is Deposit Item",
			"read_only": 1
		},
	],
    "Item Default": [
		{
			"depends_on": "eval:parent.is_deposit_item",
			"fieldname": "purchase_deposit_account",
			"fieldtype": "Link",
			"insert_after": "column_break_r6eft",
			"label": "Purchase Deposit Account",
			"link_filters": "[[\"Account\",\"root_type\",\"=\",\"Asset\"]]",
			"options": "Account"
		},
		{
			"depends_on": "eval:parent.is_deposit_item",
			"fieldname": "sales_deposit_account",
			"fieldtype": "Link",
			"insert_after": "deposit_defaults",
			"label": "Sales Deposit Account",
			"link_filters": "[[\"Account\",\"root_type\",\"=\",\"Liability\"]]",
			"options": "Account"
		},
		{
			"fieldname": "deposit_defaults",
			"fieldtype": "Section Break",
			"insert_after": "deferred_revenue_account",
			"label": "Deposit Defaults"
		},
		{
			"fieldname": "column_break_deposit_account",
			"fieldtype": "Column Break",
			"insert_after": "sales_deposit_account"
		},
	],
}