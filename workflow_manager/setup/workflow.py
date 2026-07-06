import frappe

def setup_workflow():
    # 1. Create Workflow States if they don't exist
    states = [
        "Draft", 
        "Pending Debit Note Approval", 
        "Submitted", 
        "Cancelled",
        "Pending Approval",
        "Pending Fix",
        "Approved"
    ]
    for s in states:
        if not frappe.db.exists("Workflow State", s):
            doc = frappe.new_doc("Workflow State")
            doc.workflow_state_name = s
            doc.insert(ignore_permissions=True)

    # 2. Create Workflow Action Masters if they don't exist
    actions = ["Submit", "Approve", "Reject", "Cancel", "Submit for Approval", "Pending Recorrection"]
    for a in actions:
        if not frappe.db.exists("Workflow Action Master", a):
            doc = frappe.new_doc("Workflow Action Master")
            doc.workflow_action_name = a
            doc.insert(ignore_permissions=True)

    # 3. Create or update Sales Invoice Workflow
    setup_sales_invoice_workflow()

    # 4. Create or update Purchase Invoice Workflow
    setup_purchase_invoice_workflow()


def setup_sales_invoice_workflow():
    workflow_name = "Sales Invoice Return Workflow"
    
    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Sales Invoice"
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.workflow_state_field = "workflow_state"

    # Set states
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Pending Debit Note Approval", "doc_status": "0", "allow_edit": "Accounts Approver"})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": "Accounts Approver"})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": "Accounts Approver"})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": "Accounts Approver"})

    # Set transitions
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Pending Debit Note Approval",
        "allowed": "All",
        "condition": "doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0"
    })
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "not (doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0)"
    })
    workflow.append("transitions", {
        "state": "Pending Debit Note Approval",
        "action": "Approve",
        "next_state": "Submitted",
        "allowed": "Accounts Approver"
    })
    workflow.append("transitions", {
        "state": "Pending Debit Note Approval",
        "action": "Pending Recorrection",
        "next_state": "Pending Fix",
        "allowed": "Accounts Approver"
    })
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Pending Debit Note Approval",
        "allowed": "All",
        "condition": "doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0"
    })
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "not (doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0)"
    })
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": "Accounts Approver"
    })

    workflow.insert(ignore_permissions=True)


def setup_purchase_invoice_workflow():
    workflow_name = "Purchase Invoice Approval"
    
    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Purchase Invoice"
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.workflow_state_field = "workflow_state"

    # Set states
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Pending Approval", "doc_status": "0", "allow_edit": "Accounts Approver"})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": "Accounts Approver"})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": "Accounts Approver"})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": "Accounts Approver"})

    # Set transitions
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_wf_pending_approval == 1"
    })
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "Accounts Approver",
        "condition": "doc.custom_wf_direct_submit == 1"
    })
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Pending Recorrection",
        "next_state": "Pending Fix",
        "allowed": "Accounts Approver"
    })
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_wf_pending_approval == 1"
    })
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Approve",
        "next_state": "Approved",
        "allowed": "Accounts Approver"
    })
    workflow.append("transitions", {
        "state": "Approved",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "Accounts Approver"
    })
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": "Accounts Approver"
    })

    workflow.insert(ignore_permissions=True)
