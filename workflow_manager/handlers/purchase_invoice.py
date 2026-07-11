import frappe
from workflow_manager.mappers.purchase_receipt import map_receipt_fields_to_invoice

def validate(doc):
    """
    Validation logic for Purchase Invoice.
    """
    populate_workflow_fields(doc)
    map_receipt_fields_to_invoice(doc)

def before_save(doc):
    """
    Pre-save logic for Purchase Invoice.
    """
    populate_workflow_fields(doc)
    map_receipt_fields_to_invoice(doc)


def before_submit(doc):
    """
    Submission validation for Purchase Invoice.
    Ensures that workflow conditions and permissions are respected.
    """
    # Recompute to ensure data integrity
    populate_workflow_fields(doc)

    # Check if workflow is enabled
    settings = frappe.get_single("Workflow Settings")
    if not settings.enable_purchase_invoice_approval_workflow:
        return

    approver_role = settings.approver_role or "Accounts Approver"

    # Only enforce approval flow for PIs that have items without a Purchase Order
    if doc.custom_wf_pending_approval == 1:
        db_state = frappe.db.get_value("Purchase Invoice", doc.name, "workflow_state") if doc.name else None

        # Must be in Approved state before submission is allowed
        if db_state != "Approved":
            frappe.throw(
                "Purchase Invoice requires approval because it contains items without a Purchase Order. "
                "Please use 'Submit for Approval' and wait for the approver to approve.",
                frappe.ValidationError
            )

        # Only the approver role (or Administrator) can submit an approved no-PO PI
        user_roles = frappe.get_roles(frappe.session.user)
        if approver_role not in user_roles and frappe.session.user != "Administrator":
            frappe.throw(
                f"Only users with the '{approver_role}' role can submit a Purchase Invoice "
                "that contains items without a Purchase Order.",
                frappe.PermissionError
            )

    # For PO-linked or internal supplier PIs, any user can submit directly — no restriction.


def populate_workflow_fields(doc):
    """
    Evaluates and sets generic workflow flags for Purchase Invoice based on Workflow Settings.
    """
    # Check if workflow is enabled
    settings = frappe.get_single("Workflow Settings")
    if not settings.enable_purchase_invoice_approval_workflow:
        # Reset fields if disabled
        doc.custom_wf_pending_approval = 0
        doc.custom_wf_direct_submit = 0
        doc.custom_wf_flag_1 = 0
        doc.custom_wf_flag_2 = 0
        doc.custom_wf_flag_3 = 0
        doc.custom_wf_processed = 0
        return

    # Check child table items
    has_items_without_po = False
    has_items_with_po = False

    if doc.items:
        has_items_without_po = any(not row.purchase_order for row in doc.items)
        has_items_with_po = any(row.purchase_order for row in doc.items)

    # Check supplier
    is_internal_supplier = False
    if doc.supplier:
        is_internal_supplier = bool(frappe.db.get_value("Supplier", doc.supplier, "is_bns_internal_supplier"))

    # Map conditions to generic workflow flags
    doc.custom_wf_flag_1 = 1 if has_items_without_po else 0
    doc.custom_wf_flag_2 = 1 if has_items_with_po else 0
    doc.custom_wf_flag_3 = 1 if is_internal_supplier else 0

    # Compute workflow pathways
    doc.custom_wf_pending_approval = 1 if (has_items_without_po and not is_internal_supplier) else 0
    doc.custom_wf_direct_submit = 1 if (has_items_with_po or is_internal_supplier) else 0
    doc.custom_wf_processed = 1

@frappe.whitelist()
def handle_recorrection(docname, correction_message):
    if not correction_message:
        frappe.throw("Correction Message is required", frappe.ValidationError)

    doc = frappe.get_doc("Purchase Invoice", docname)

    # Validate that current user has permission to perform the transition
    from frappe.model.workflow import get_transitions, get_workflow
    workflow = get_workflow(doc.doctype)
    transitions = get_transitions(doc, workflow)

    allowed_actions = [t.action for t in transitions]
    if "Pending Recorrection" not in allowed_actions:
        frappe.throw(
            "You are not authorized to perform the 'Pending Recorrection' action, or the document is not in the correct state.",
            frappe.PermissionError
        )

    # 1. Apply the workflow transition "Pending Recorrection"
    from frappe.model.workflow import apply_workflow
    apply_workflow(doc, "Pending Recorrection")

    # 2. Automatically create a Comment on the same Purchase Invoice
    comment_text = f"Correction requested by Accounts Approver.\n\nReason:\n{correction_message}"
    doc.add_comment(
        comment_type="Comment",
        text=comment_text
    )

    # 3. Send Raven notification to the document creator (doc.owner)
    from workflow_manager.utils.notifications import send_raven_notification
    notification_message = (
        f"Your Purchase Invoice {doc.name} has been sent back for correction.\n\n"
        f"Reason:\n{correction_message}"
    )
    send_raven_notification(
        recipient=doc.owner,
        message=notification_message,
        link_doctype="Purchase Invoice",
        link_document=doc.name
    )

    return {"status": "success"}

