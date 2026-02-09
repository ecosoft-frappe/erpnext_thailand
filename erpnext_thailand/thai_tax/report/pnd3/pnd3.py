# Copyright (c) 2023, Kitti U. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import Case, CustomFunction
from frappe.query_builder.custom import ConstantColumn


CUSTOM_FIELDS = [
    "room_no", "floor", "building_name", "house_number", "village",
    "moo", "alley_lane", "intersection", "road"
]

BASE_COLUMNS = [
    {"label": _("No."),                 "fieldname": "no",              "fieldtype": "Int",     "width": 0},
    {"label": _("Supplier Tax ID"),     "fieldname": "supplier_tax_id", "fieldtype": "Data",    "width": 0},
    {"label": _("Branch"),              "fieldname": "branch",          "fieldtype": "Data",    "width": 0},
    {"label": _("Supplier Name"),       "fieldname": "supplier_name",   "fieldtype": "Data",    "width": 0},
    {"label": _("Title"),       		"fieldname": "title",   		"fieldtype": "Data",    "width": 0},
    {"label": _("Address"),             "fieldname": "address_line1",   "fieldtype": "Data",    "width": 0},
]

OTHER_COLUMNS = [
    {"label": _("Postal Code"),         "fieldname": "pincode",         "fieldtype": "Data",            "width": 0},
    {"label": _("Date"),                "fieldname": "date",            "fieldtype": "Date",            "width": 0},
    {"label": _("Description"),         "fieldname": "description",     "fieldtype": "Data",            "width": 0},
    {"label": _("Tax Base"),            "fieldname": "tax_base",        "fieldtype": "Currency",        "options":  "Company:company:default_currency", "width": 0},
    {"label": _("Tax Rate"),            "fieldname": "tax_rate",        "fieldtype": "Int",             "width": 0},
    {"label": _("Tax Amount"),          "fieldname": "tax_amount",      "fieldtype": "Currency",        "options":  "Company:company:default_currency", "width": 0},
    {"label": _("Tax Payer"),           "fieldname": "tax_payer",       "fieldtype": "Data",            "width": 0},
    {"label": _("WHT Cert."),           "fieldname": "name",            "fieldtype": "Link",            "options":  "Withholding Tax Cert",             "width": 0},
    {"label": _("Voucher Type"),        "fieldname": "voucher_type",    "fieldtype": "Data",            "width": 0},
    {"label": _("Voucher No"),          "fieldname": "voucher_no",      "fieldtype": "Dynamic Link",    "options":  "voucher_type",                     "width": 0},
]

def execute(filters=None):
    address = frappe.get_meta("Address")
    has_custom_fields = all(field in [df.fieldname for df in address.fields] for field in CUSTOM_FIELDS)

    columns = get_columns(has_custom_fields)
    data = get_data(filters, has_custom_fields)
    return columns, data, None, None, None

def get_columns(has_custom_fields):
    address_cols = get_address_columns(has_custom_fields)
    return BASE_COLUMNS + address_cols + OTHER_COLUMNS

def get_address_columns(has_custom_fields):
    if has_custom_fields:
        return [
            {"label": _("Building Name"), "fieldname": "building_name", "fieldtype": "Data", "width": 0},
            {"label": _("Room No."), "fieldname": "room_no", "fieldtype": "Data", "width": 0},
            {"label": _("Floor"), "fieldname": "floor", "fieldtype": "Data", "width": 0},
            {"label": _("Village"), "fieldname": "village", "fieldtype": "Data", "width": 0},
            {"label": _("House Number"), "fieldname": "house_number", "fieldtype": "Data", "width": 0},
            {"label": _("Moo"), "fieldname": "moo", "fieldtype": "Data", "width": 0},
            {"label": _("Alley/Lane"), "fieldname": "alley_lane", "fieldtype": "Data", "width": 0},
            {"label": _("Intersection"), "fieldname": "intersection", "fieldtype": "Data", "width": 0},
            {"label": _("Road"), "fieldname": "road", "fieldtype": "Data", "width": 0},
            {"label": _("Subdistrict"), "fieldname": "city", "fieldtype": "Data", "width": 0},
            {"label": _("District"), "fieldname": "county", "fieldtype": "Data", "width": 0},
            {"label": _("Province"), "fieldname": "state", "fieldtype": "Data", "width": 0},
        ]
    else:
        return [
            {"label": _("Subdistrict"), "fieldname": "city", "fieldtype": "Data", "width": 0},
            {"label": _("District"), "fieldname": "county", "fieldtype": "Data", "width": 0},
            {"label": _("Province"), "fieldname": "state", "fieldtype": "Data", "width": 0},
        ]

def get_data(filters, has_custom_fields):
    query = build_query(filters, has_custom_fields)
    result = query.run(as_dict=True)

    # Add row number
    for i, r in enumerate(result, start=1):
        r["no"] = i

    return result

def build_query(filters, has_custom_fields):
    wht_cert = frappe.qb.DocType("Withholding Tax Cert")
    wht_items = frappe.qb.DocType("Withholding Tax Items")
    supplier = frappe.qb.DocType("Supplier")
    address = frappe.qb.DocType("Address")
    company_address = address.as_("company_address")

    round = CustomFunction("round", ["value", "digit"])
    month = CustomFunction("month", ["date"])
    year = CustomFunction("year", ["date"])

    address_fields = (
        [
            address.address_line1.as_("address_line1"),
            address.room_no.as_("room_no"),
            address.floor.as_("floor"),
            address.building_name.as_("building_name"),
            address.house_number.as_("house_number"),
            address.village.as_("village"),
            address.moo.as_("moo"),
            address.alley_lane.as_("alley_lane"),
            address.intersection.as_("intersection"),
            address.road.as_("road"),
            address.city.as_("city"),
            address.county.as_("county"),
            address.state.as_("state"),
        ]
        if has_custom_fields
        else [
            address.address_line1.as_("address_line1"),
            address.city.as_("city"),
            address.county.as_("county"),
            address.state.as_("state"),
        ]
    )

    query = (
        frappe.qb.from_(wht_cert)
        .join(wht_items).on(wht_items.parent == wht_cert.name)
        .join(supplier).on(supplier.name == wht_cert.supplier)
        .left_join(address).on(address.name == wht_cert.supplier_address)
        .left_join(company_address).on(company_address.name == wht_cert.company_address)
        .select(
            supplier.tax_id.as_("supplier_tax_id"),
            supplier.branch_code.as_("branch"),
            ConstantColumn("").as_("title"),
            supplier.supplier_name.as_("supplier_name"),
            *address_fields,
            address.pincode.as_("pincode"),
            wht_cert.date.as_("date"),
            wht_items.description.as_("description"),
            round(wht_items.tax_base, 2).as_("tax_base"),
            wht_items.tax_rate.as_("tax_rate"),
            round(wht_items.tax_amount, 2).as_("tax_amount"),
            Case()
            .when(wht_cert.tax_payer == "Withholding", "1")
            .when(wht_cert.tax_payer == "Paid One Time", "3")
            .else_(wht_cert.tax_payer)
            .as_("tax_payer"),
            wht_cert.name.as_("name"),
            wht_cert.voucher_type.as_("voucher_type"),
            wht_cert.voucher_no.as_("voucher_no"),
            wht_cert.company_tax_id.as_("company_tax_id"),
            company_address.branch_code.as_("company_branch"),
        )
        .distinct()
        .where(
            (wht_cert.docstatus == 1)
            & (wht_cert.income_tax_form == "PND53")
            & (month(wht_cert.date) == filters.get("month"))
            & (year(wht_cert.date) == filters.get("year"))
        )
        .orderby(wht_cert.date, wht_cert.name)
    )

    if filters.get("company_address"):
        query = query.where(wht_cert.company_address == filters.get("company_address"))

    return query
