import frappe

DEFAULT_APPROVER_ROLE = "Accounts Approver"


def get_approver_role():
    """Return the approver role from Workflow Settings, falling back to default."""
    try:
        settings = frappe.get_single("Workflow Settings")
        return settings.approver_role or DEFAULT_APPROVER_ROLE
    except Exception:
        return DEFAULT_APPROVER_ROLE


def setup_workflow():
    # 1. Create Workflow States if they don't exist
    states = [
        "Draft",
        "Pending Debit Note Approval",
        "Submitted",
        "Cancelled",
        "Pending Approval",
        "Pending Fix",
        "Approved",
        "Rejected"
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

    approver_role = get_approver_role()

    # 3. Create or update Sales Invoice Workflow
    setup_sales_invoice_workflow(approver_role)

    # 4. Create or update Purchase Invoice Workflow
    setup_purchase_invoice_workflow(approver_role)

    # 5. Create or update Journal Entry Workflow
    setup_journal_entry_workflow(approver_role)


def setup_sales_invoice_workflow(approver_role=None):
    if approver_role is None:
        approver_role = get_approver_role()

    workflow_name = "Sales Invoice Return Workflow"

    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Sales Invoice"
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.workflow_state_field = "workflow_state"

    # States
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Pending Debit Note Approval", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": approver_role})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": approver_role})

    # Transitions
    # Draft → Pending Debit Note Approval (B2B return missing debit note)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Pending Debit Note Approval",
        "allowed": "All",
        "condition": "doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0"
    })
    # Draft → Submitted (all other cases — non-B2B or debit note complete)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "not (doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0)"
    })
    # Pending Debit Note Approval → Submitted (approver approves)
    workflow.append("transitions", {
        "state": "Pending Debit Note Approval",
        "action": "Approve",
        "next_state": "Submitted",
        "allowed": approver_role
    })
    # Pending Debit Note Approval → Pending Fix (approver requests correction)
    workflow.append("transitions", {
        "state": "Pending Debit Note Approval",
        "action": "Pending Recorrection",
        "next_state": "Pending Fix",
        "allowed": approver_role
    })
    # Pending Fix → Pending Debit Note Approval (re-submit for approval)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Pending Debit Note Approval",
        "allowed": "All",
        "condition": "doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0"
    })
    # Pending Fix → Submitted (debit note now complete)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "not (doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0)"
    })
    # Submitted → Cancelled
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": approver_role
    })

    workflow.insert(ignore_permissions=True)


def setup_purchase_invoice_workflow(approver_role=None):
    if approver_role is None:
        approver_role = get_approver_role()

    workflow_name = "Purchase Invoice Approval"

    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Purchase Invoice"
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.workflow_state_field = "workflow_state"

    # States
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Pending Approval", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": approver_role})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": approver_role})

    # Transitions

    # Draft → Pending Approval (items without PO — needs approval)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_wf_pending_approval == 1"
    })
    # Draft → Submitted (PO-linked or internal supplier — any user can submit directly)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "doc.custom_wf_direct_submit == 1"
    })
    # Draft → Submitted (approver can also directly submit direct-submit PIs)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": approver_role,
        "condition": "doc.custom_wf_direct_submit == 1"
    })
    # Pending Approval → Pending Fix (approver requests correction)
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Pending Recorrection",
        "next_state": "Pending Fix",
        "allowed": approver_role
    })
    # Pending Fix → Pending Approval (user re-submits for approval)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_wf_pending_approval == 1"
    })
    # Pending Fix → Submitted (user fixed item, now has PO — direct submit)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "doc.custom_wf_direct_submit == 1"
    })
    # Pending Approval → Approved
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Approve",
        "next_state": "Approved",
        "allowed": approver_role
    })
    # Approved → Submitted (only approver submits an approved PI)
    workflow.append("transitions", {
        "state": "Approved",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": approver_role
    })
    # Submitted → Cancelled
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": approver_role
    })

    workflow.insert(ignore_permissions=True)


def setup_journal_entry_workflow(approver_role=None):
    if approver_role is None:
        approver_role = get_approver_role()

    workflow_name = "Journal Entry Approval Workflow"

    if frappe.db.exists("Workflow", workflow_name):
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Journal Entry"
    workflow.is_active = 1
    workflow.override_status = 0
    workflow.workflow_state_field = "workflow_state"

    # States
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Pending Approval", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Rejected", "doc_status": "0", "allow_edit": "All"})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": approver_role})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": approver_role})

    # Transitions

    # Draft → Pending Approval (suspense account debit)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_je_pending_approval == 1"
    })
    # Draft → Submitted (no suspense account — any user can submit)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "doc.custom_je_pending_approval == 0"
    })
    # Approver can also directly submit non-suspense JEs from Draft
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": approver_role,
        "condition": "doc.custom_je_pending_approval == 0"
    })
    # Pending Approval → Pending Fix
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Pending Recorrection",
        "next_state": "Pending Fix",
        "allowed": approver_role
    })
    # Pending Approval → Rejected
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Reject",
        "next_state": "Rejected",
        "allowed": approver_role
    })
    # Pending Approval → Approved
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Approve",
        "next_state": "Approved",
        "allowed": approver_role
    })
    # Pending Fix → Pending Approval (re-submit for approval, still suspense)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_je_pending_approval == 1"
    })
    # Pending Fix → Submitted (no suspense — any user can submit)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "doc.custom_je_pending_approval == 0"
    })
    # Approver can also submit non-suspense from Pending Fix
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": approver_role,
        "condition": "doc.custom_je_pending_approval == 0"
    })
    # Rejected → Pending Approval (re-submit for approval, still suspense)
    workflow.append("transitions", {
        "state": "Rejected",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": "All",
        "condition": "doc.custom_je_pending_approval == 1"
    })
    # Rejected → Submitted (no suspense — any user can submit)
    workflow.append("transitions", {
        "state": "Rejected",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": "All",
        "condition": "doc.custom_je_pending_approval == 0"
    })
    # Approver can also submit non-suspense from Rejected
    workflow.append("transitions", {
        "state": "Rejected",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": approver_role,
        "condition": "doc.custom_je_pending_approval == 0"
    })
    # Approved → Submitted (only approver submits after approval)
    workflow.append("transitions", {
        "state": "Approved",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": approver_role
    })
    # Submitted → Cancelled
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": approver_role
    })

    workflow.insert(ignore_permissions=True)
