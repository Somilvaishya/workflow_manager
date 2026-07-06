import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def setup_custom_fields():
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "custom_customer_debit_note_details_section",
                "label": "Customer Debit Note Details",
                "fieldtype": "Section Break",
                "collapsible": 1,
                "insert_after": "project",
                "depends_on": "eval:doc.is_return == 1"
            },
            {
                "fieldname": "custom_customer_debit_note_no",
                "label": "Customer Debit Note No",
                "fieldtype": "Data",
                "insert_after": "custom_customer_debit_note_details_section",
                "depends_on": "eval:doc.is_return == 1 && doc.custom_is_b2b_customer == 1"
            },
            {
                "fieldname": "custom_debit_note_attachment",
                "label": "Debit Note Attachment",
                "fieldtype": "Attach",
                "insert_after": "custom_customer_debit_note_no",
                "depends_on": "eval:doc.is_return == 1 && doc.custom_is_b2b_customer == 1"
            },
            {
                "fieldname": "custom_debit_note_details_column_break",
                "fieldtype": "Column Break",
                "insert_after": "custom_debit_note_attachment"
            },
            {
                "fieldname": "custom_debit_note_date",
                "label": "Debit Note Date",
                "fieldtype": "Date",
                "insert_after": "custom_debit_note_details_column_break",
                "depends_on": "eval:doc.is_return == 1 && doc.custom_is_b2b_customer == 1"
            },
            {
                "fieldname": "custom_is_b2b_customer",
                "label": "Is B2B Customer",
                "fieldtype": "Check",
                "insert_after": "custom_debit_note_date",
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
        ],
        "Purchase Invoice": [
            {
                "fieldname": "custom_wf_pending_approval",
                "label": "WF Pending Approval",
                "fieldtype": "Check",
                "insert_after": "is_paid",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "custom_wf_direct_submit",
                "label": "WF Direct Submit",
                "fieldtype": "Check",
                "insert_after": "custom_wf_pending_approval",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "custom_wf_flag_1",
                "label": "WF Flag 1",
                "fieldtype": "Check",
                "insert_after": "custom_wf_direct_submit",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "custom_wf_flag_2",
                "label": "WF Flag 2",
                "fieldtype": "Check",
                "insert_after": "custom_wf_flag_1",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "custom_wf_flag_3",
                "label": "WF Flag 3",
                "fieldtype": "Check",
                "insert_after": "custom_wf_flag_2",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "custom_wf_processed",
                "label": "WF Processed",
                "fieldtype": "Check",
                "insert_after": "custom_wf_flag_3",
                "hidden": 1,
                "read_only": 1
            },
            {
                "fieldname": "bns_ewaybill_date",
                "label": "e-Waybill Date",
                "fieldtype": "Date",
                "insert_after": "bill_date"
            },
            {
                "fieldname": "bns_ewaybill_attachment",
                "label": "e-Waybill",
                "fieldtype": "Attach",
                "insert_after": "bns_ewaybill_date"
            }
        ],
        "Purchase Receipt": [
            {
                "fieldname": "supplier_invoice_section",
                "label": "Supplier Invoice",
                "fieldtype": "Section Break",
                "insert_after": "lr_date",
                "collapsible": 1
            },
            {
                "fieldname": "bill_no",
                "label": "Supplier Invoice No",
                "fieldtype": "Data",
                "insert_after": "supplier_invoice_section"
            },
            {
                "fieldname": "bill_date",
                "label": "Supplier Invoice Date",
                "fieldtype": "Date",
                "insert_after": "bill_no"
            },
            {
                "fieldname": "bns_ewaybill_date",
                "label": "e-Waybill Date",
                "fieldtype": "Date",
                "insert_after": "bill_date"
            },
            {
                "fieldname": "bns_ewaybill_attachment",
                "label": "e-Waybill",
                "fieldtype": "Attach",
                "insert_after": "bns_ewaybill_date"
            }
        ]
    }
    
    create_custom_fields(custom_fields, update=True)

