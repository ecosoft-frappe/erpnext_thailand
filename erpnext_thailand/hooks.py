from . import __version__ as app_version

app_name = "erpnext_thailand"
app_title = "ERPNext Thailand"
app_publisher = "Ecosoft"
app_description = "Thailand Localization"
app_email = "kittiu@ecosoft.co.th"
app_license = "MIT"
required_apps = ["erpnext"]


naming_series_variables = {
	"YYYY-DATE": "erpnext_thailand.custom.naming.parse_naming_series_variable",
	"YY-DATE": "erpnext_thailand.custom.naming.parse_naming_series_variable",
	"MM-DATE": "erpnext_thailand.custom.naming.parse_naming_series_variable",
	"DD-DATE": "erpnext_thailand.custom.naming.parse_naming_series_variable",
	"WW-DATE": "erpnext_thailand.custom.naming.parse_naming_series_variable",
}

fixtures = [
	{
		"doctype": "Withholding Tax Type Of Income",
		"filters": [
			[
				"name",
				"in",
				(
        			"1", "2", "3", "4", "4.1.1", "4.1.2", "4.1.3", "4.1.4",
        			"4.2.1", "4.2.2", "4.2.3", "4.2.4", "4.2.5", "5", "6",
				)
			]
		],
	},
    {
		"doctype": "Property Setter",
		"filters": [
			[
				"name",
				"in",
				(
					"Currency Exchange Settings-service_provider-options",
				),
			]
		],
	}
]


# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_thailand/css/erpnext_thailand.css"
# app_include_js = "/assets/erpnext_thailand/js/erpnext_thailand.js"
app_include_js = "erpnext_thailand.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_thailand/css/erpnext_thailand.css"
# web_include_js = "/assets/erpnext_thailand/js/erpnext_thailand.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnext_thailand/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}

doctype_js = {
	"Journal Entry": "public/js/journal_entry.js",
	"Payment Entry": "public/js/payment_entry.js",
	"Expense Claim": "public/js/expense_claim.js",
	"Purchase Invoice": "public/js/purchase_invoice.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Purchase Tax Invoice": "public/js/purchase_tax_invoice.js",
	"Sales Tax Invoice": "public/js/sales_tax_invoice.js",
	"Address": "public/js/address.js",
    "Currency Exchange Settings": "public/js/currency_exchange_settings.js",
}


# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#     "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#     "methods": "erpnext_thailand.utils.jinja_methods",
#     "filters": "erpnext_thailand.utils.jinja_filters"
# }

jinja = {
	"methods": [
		"erpnext_thailand.utils.amount_in_bahttext",
		"erpnext_thailand.utils.full_thai_date",
	],
}

# Installation
# ------------

# before_install = "erpnext_thailand.install.before_install"
after_install = "erpnext_thailand.install.after_install"
after_app_install = "erpnext_thailand.install.after_app_install"

# Uninstallation
# ------------

# before_uninstall = "erpnext_thailand.uninstall.before_uninstall"
# after_uninstall = "erpnext_thailand.uninstall.after_uninstall"
before_app_uninstall = "erpnext_thailand.uninstall.before_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_thailand.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#     "Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#     "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes
override_doctype_class = {
	"Employee Advance": "erpnext_thailand.custom.employee_advance.ThaiTaxEmployeeAdvance",
}

# Document Events
# ---------------
# Hook on document methods and events


doc_events = {
	"GL Entry": {
		"after_insert": "erpnext_thailand.custom.custom_api.create_tax_invoice_on_gl_tax",
	},
	"Payment Entry": {
		"validate": "erpnext_thailand.custom.custom_api.validate_company_address",
		"on_update": "erpnext_thailand.custom.custom_api.clear_invoice_undue_tax",
        "on_submit": [
            "erpnext_thailand.custom.payment_entry.reconcile_undue_tax",
            "erpnext_thailand.custom.payment_entry.update_sales_billing_outstanding_amount",
        ],
        "on_cancel": [
            "erpnext_thailand.custom.payment_entry.update_sales_billing_outstanding_amount",
        ],
    },
    "Unreconcile Payment": {
        "on_submit": "erpnext_thailand.custom.unreconcile_payment.unreconcile_undue_tax",
	},
    "Sales Invoice": {
        "on_submit": "erpnext_thailand.custom.custom_api.create_sales_tax_invoice_on_zero_tax",
		"before_cancel": "erpnext_thailand.custom.custom_api.cancel_related_tax_invoice",
    },
	"Purchase Invoice": {
		"after_insert": "erpnext_thailand.custom.custom_api.validate_tax_invoice",
		"on_update": "erpnext_thailand.custom.custom_api.validate_tax_invoice",
	},
	"Expense Claim": {
		"after_insert": "erpnext_thailand.custom.custom_api.validate_tax_invoice",
		"on_update": "erpnext_thailand.custom.custom_api.validate_tax_invoice",
	},
	"Journal Entry": {
		"on_update": "erpnext_thailand.custom.custom_api.prepare_journal_entry_tax_invoice_detail",
		"on_submit": "erpnext_thailand.custom.journal_entry.reconcile_undue_tax",
	},
	"Print Format": {
		"before_validate": "erpnext_thailand.custom.print_format.allow_update_standard",
	},
    "Address": {
        "on_update": "erpnext_thailand.custom.address.update_tax_info_in_linked_doc"
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
#     "all": [
#         "erpnext_thailand.tasks.all"
#     ],
#     "daily": [
#         "erpnext_thailand.tasks.daily"
#     ],
#     "hourly": [
#         "erpnext_thailand.tasks.hourly"
#     ],
#     "weekly": [
#         "erpnext_thailand.tasks.weekly"
#     ],
#     "monthly": [
#         "erpnext_thailand.tasks.monthly"
#     ],
# }

# Testing
# -------

# before_tests = "erpnext_thailand.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
    "erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents": "erpnext_thailand.custom.payment_entry.get_outstanding_reference_documents"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps

override_doctype_dashboards = {
	"Purchase Invoice": "erpnext_thailand.custom.dashboard_overrides.get_dashboard_data_for_purchase_invoice",
	"Sales Invoice": "erpnext_thailand.custom.dashboard_overrides.get_dashboard_data_for_sales_invoice",
	"Expense Claim": "erpnext_thailand.custom.dashboard_overrides.get_dashboard_data_for_expense_claim",
	"Payment Entry": "erpnext_thailand.custom.dashboard_overrides.get_dashboard_data_for_payment_entry",
}

# override_doctype_dashboards = {
#     "Task": "erpnext_thailand.task.get_dashboard_data"
# }
# exempt linked doctypes from being automatically cancelled
#
auto_cancel_exempted_doctypes = ["Sales Tax Invoice", "Purchase Tax Invoice"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpnext_thailand.utils.before_request"]
# after_request = ["erpnext_thailand.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpnext_thailand.utils.before_job"]
# after_job = ["erpnext_thailand.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_2}",
#         "filter_by": "{filter_by}",
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_3}",
#         "strict": False,
#     },
#     {
#         "doctype": "{doctype_4}"
#     }
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#     "erpnext_thailand.auth.validate"
# ]
