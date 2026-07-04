import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_custom_fields():
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "custom_customer_debit_note_no",
                "label": "Customer Debit Note No",
                "fieldtype": "Data",
                "insert_after": "project",
                "depends_on": "eval:doc.is_return == 1 && doc.custom_is_b2b_customer == 1"
            },
            {
                "fieldname": "custom_debit_note_date",
                "label": "Debit Note Date",
                "fieldtype": "Date",
                "insert_after": "custom_customer_debit_note_no",
                "depends_on": "eval:doc.is_return == 1 && doc.custom_is_b2b_customer == 1"
            },
            {
                "fieldname": "custom_debit_note_attachment",
                "label": "Debit Note Attachment",
                "fieldtype": "Attach",
                "insert_after": "custom_debit_note_date",
                "depends_on": "eval:doc.is_return == 1 && doc.custom_is_b2b_customer == 1"
            },
            {
                "fieldname": "custom_is_b2b_customer",
                "label": "Is B2B Customer",
                "fieldtype": "Check",
                "insert_after": "custom_debit_note_attachment",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "custom_debit_note_complete",
                "label": "Debit Note Complete",
                "fieldtype": "Check",
                "insert_after": "custom_is_b2b_customer",
                "hidden": 1,
                "read_only": 1
            }
        ]
    }
    
    create_custom_fields(custom_fields, update=True)
