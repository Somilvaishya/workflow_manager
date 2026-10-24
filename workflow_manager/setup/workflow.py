import frappe

DEFAULT_APPROVER_ROLE = "Accounts Approver"


DEFAULT_NORMAL_ROLE = "All"


# Maps each Workflow Settings enable checkbox to the workflow it controls.
# This is the single source of truth; Workflow Settings imports it from here.
WORKFLOW_MAP = {
    "enable_sales_invoice_approval_workflow": "Sales Invoice Return Workflow",
    "enable_purchase_invoice_approval_workflow": "Purchase Invoice Approval",
    "enable_journal_entry_approval_workflow": "Journal Entry Approval Workflow",
}


def get_settings():
    """Return Workflow Settings, or None when it is not available yet (e.g. first install)."""
    try:
        return frappe.get_single("Workflow Settings")
    except Exception:
        return None


def is_workflow_enabled(fieldname):
    """Return True when the given Workflow Settings enable checkbox is ticked."""
    settings = get_settings()
    return bool(settings and settings.get(fieldname))


def get_normal_role():
    settings = get_settings()
    return (settings and settings.normal_role) or DEFAULT_NORMAL_ROLE


def ensure_role(role_name):
    """Create a desk Role when it is missing; the workflows link to it in states and transitions."""
    if role_name and not frappe.db.exists("Role", role_name):
        frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
            ignore_permissions=True
        )


def get_approver_role():
    """Return the approver role from Workflow Settings, falling back to default."""
    settings = get_settings()
    return (settings and settings.approver_role) or DEFAULT_APPROVER_ROLE


def set_workflow_active(workflow_name, enabled):
    """
    Activate or deactivate a workflow, keeping Frappe's "one active workflow per
    DocType" rule intact (Workflow.set_active() only runs on a full document save,
    which we deliberately avoid here).
    """
    if not frappe.db.exists("Workflow", workflow_name):
        return

    is_active = 1 if enabled else 0
    if frappe.db.get_value("Workflow", workflow_name, "is_active") == is_active:
        return

    doctype = frappe.db.get_value("Workflow", workflow_name, "document_type")

    if is_active:
        others = frappe.get_all(
            "Workflow",
            filters={"document_type": doctype, "is_active": 1, "name": ["!=", workflow_name]},
            pluck="name",
        )
        for other in others:
            frappe.db.set_value("Workflow", other, "is_active", 0)

    frappe.db.set_value("Workflow", workflow_name, "is_active", is_active)
    # get_workflow_name() caches the active workflow per DocType.
    frappe.clear_cache(doctype=doctype)


def sync_workflow_active_flags():
    """Align every workflow's is_active flag with its Workflow Settings checkbox."""
    settings = get_settings()
    if not settings:
        return
    for fieldname, workflow_name in WORKFLOW_MAP.items():
        set_workflow_active(workflow_name, settings.get(fieldname))


def setup_workflow(force=False):
    """
    Provision the workflow states, actions and the three workflows.

    force=False (used on migrate) only creates workflows that are missing, so
    manual tuning done in the Workflow UI survives a `bench migrate`.
    force=True (used on install, or from Workflow Settings) rebuilds them from
    this file, discarding any manual edits.
    """
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
    normal_role = get_normal_role()
    ensure_role(approver_role)

    # 3. Create or update Sales Invoice Workflow
    setup_sales_invoice_workflow(approver_role, normal_role, force=force)

    # 4. Create or update Purchase Invoice Workflow
    setup_purchase_invoice_workflow(approver_role, normal_role, force=force)

    # 5. Create or update Journal Entry Workflow
    setup_journal_entry_workflow(approver_role, normal_role, force=force)

    # 6. Make sure is_active matches the Workflow Settings checkboxes
    sync_workflow_active_flags()


def setup_sales_invoice_workflow(approver_role=None, normal_role=None, force=True):
    if approver_role is None:
        approver_role = get_approver_role()
    if normal_role is None:
        normal_role = get_normal_role()

    workflow_name = "Sales Invoice Return Workflow"

    if frappe.db.exists("Workflow", workflow_name):
        if not force:
            # Never clobber an existing workflow on migrate — manual edits made in
            # the Workflow UI must survive.
            return
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Sales Invoice"
    # A brand-new workflow follows its Workflow Settings checkbox rather than
    # switching itself on unconditionally.
    workflow.is_active = 1 if is_workflow_enabled("enable_sales_invoice_approval_workflow") else 0
    workflow.override_status = 1
    workflow.workflow_state_field = "workflow_state"

    # States
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Pending Debit Note Approval", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": normal_role})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": normal_role})

    # Approval needed condition:
    # - Must be a return (is_return == 1)
    # - AND B2B customer (custom_is_b2b_customer == 1, which already excludes internal customers)
    # - AND debit note incomplete (custom_debit_note_complete == 0)
    needs_approval = (
        "doc.is_return == 1 and doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0"
    )
    no_approval_needed = f"not ({needs_approval})"

    # Transitions

    # Draft → Pending Debit Note Approval (B2B return, incomplete debit note, non-internal customer)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Pending Debit Note Approval",
        "allowed": normal_role,
        "condition": needs_approval
    })
    # Draft → Submitted (everything else: normal SI, B2C return, internal customer, complete debit note)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
        "condition": no_approval_needed
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
        "allowed": normal_role,
        "condition": needs_approval
    })
    # Pending Fix → Submitted (debit note now complete or conditions changed)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
        "condition": no_approval_needed
    })
    # Submitted → Cancelled
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": normal_role
    })

    workflow.insert(ignore_permissions=True)


def setup_purchase_invoice_workflow(approver_role=None, normal_role=None, force=True):
    if approver_role is None:
        approver_role = get_approver_role()
    if normal_role is None:
        normal_role = get_normal_role()

    workflow_name = "Purchase Invoice Approval"

    if frappe.db.exists("Workflow", workflow_name):
        if not force:
            # Never clobber an existing workflow on migrate — manual edits made in
            # the Workflow UI must survive.
            return
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Purchase Invoice"
    # A brand-new workflow follows its Workflow Settings checkbox rather than
    # switching itself on unconditionally.
    workflow.is_active = 1 if is_workflow_enabled("enable_purchase_invoice_approval_workflow") else 0
    workflow.override_status = 1
    workflow.workflow_state_field = "workflow_state"

    # States
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Pending Approval", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": normal_role})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": normal_role})

    # Transitions

    # Draft → Pending Approval (items without PO — needs approval)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": normal_role,
        "condition": "doc.custom_wf_pending_approval == 1"
    })
    # Draft → Submitted (PO-linked or internal supplier — any user can submit directly)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
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
        "allowed": normal_role,
        "condition": "doc.custom_wf_pending_approval == 1"
    })
    # Pending Fix → Submitted (user fixed item, now has PO — direct submit)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
        "condition": "doc.custom_wf_direct_submit == 1"
    })
    # Pending Approval → Approved
    workflow.append("transitions", {
        "state": "Pending Approval",
        "action": "Approve",
        "next_state": "Approved",
        "allowed": approver_role
    })
    # Approved → Submitted (any user may submit once it has been approved)
    workflow.append("transitions", {
        "state": "Approved",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role
    })
    # Submitted → Cancelled
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": normal_role
    })

    workflow.insert(ignore_permissions=True)


def setup_journal_entry_workflow(approver_role=None, normal_role=None, force=True):
    if approver_role is None:
        approver_role = get_approver_role()
    if normal_role is None:
        normal_role = get_normal_role()

    workflow_name = "Journal Entry Approval Workflow"

    if frappe.db.exists("Workflow", workflow_name):
        if not force:
            # Never clobber an existing workflow on migrate — manual edits made in
            # the Workflow UI must survive.
            return
        frappe.delete_doc("Workflow", workflow_name, ignore_permissions=True)

    workflow = frappe.new_doc("Workflow")
    workflow.workflow_name = workflow_name
    workflow.document_type = "Journal Entry"
    # A brand-new workflow follows its Workflow Settings checkbox rather than
    # switching itself on unconditionally.
    workflow.is_active = 1 if is_workflow_enabled("enable_journal_entry_approval_workflow") else 0
    workflow.override_status = 1
    workflow.workflow_state_field = "workflow_state"

    # States
    workflow.append("states", {"state": "Draft", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Pending Approval", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Pending Fix", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Approved", "doc_status": "0", "allow_edit": approver_role})
    workflow.append("states", {"state": "Rejected", "doc_status": "0", "allow_edit": normal_role})
    workflow.append("states", {"state": "Submitted", "doc_status": "1", "allow_edit": normal_role})
    workflow.append("states", {"state": "Cancelled", "doc_status": "2", "allow_edit": normal_role})

    # Transitions

    # Draft → Pending Approval (suspense account debit)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit for Approval",
        "next_state": "Pending Approval",
        "allowed": normal_role,
        "condition": "doc.custom_je_pending_approval == 1"
    })
    # Draft → Submitted (no suspense account — any user can submit)
    workflow.append("transitions", {
        "state": "Draft",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
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
        "allowed": normal_role,
        "condition": "doc.custom_je_pending_approval == 1"
    })
    # Pending Fix → Submitted (no suspense — any user can submit)
    workflow.append("transitions", {
        "state": "Pending Fix",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
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
        "allowed": normal_role,
        "condition": "doc.custom_je_pending_approval == 1"
    })
    # Rejected → Submitted (no suspense — any user can submit)
    workflow.append("transitions", {
        "state": "Rejected",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role,
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
    # Approved → Submitted (any user may submit once it has been approved)
    workflow.append("transitions", {
        "state": "Approved",
        "action": "Submit",
        "next_state": "Submitted",
        "allowed": normal_role
    })
    # Submitted → Cancelled
    workflow.append("transitions", {
        "state": "Submitted",
        "action": "Cancel",
        "next_state": "Cancelled",
        "allowed": normal_role
    })

    workflow.insert(ignore_permissions=True)
