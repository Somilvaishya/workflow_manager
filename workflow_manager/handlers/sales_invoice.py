import frappe

def validate(doc):
    """
    Validation logic for Sales Invoice.
    Runs on validate event.
    """
    populate_workflow_fields(doc)

def before_save(doc):
    """
    Pre-save logic for Sales Invoice.
    Runs on before_save event.
    """
    populate_workflow_fields(doc)

def before_submit(doc):
    """
    Submission validation for Sales Invoice.
    Enforces that B2B Customer Return (Debit Note) approval rules are met.
    """
    # Recalculate fields to ensure integrity before submit
    populate_workflow_fields(doc)

    settings = frappe.get_single("Workflow Settings")
    approver_role = settings.approver_role or "Accounts Approver"

    if doc.is_return == 1 and doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0:
        # Check database value of the workflow state to see what it was before transition
        db_state = frappe.db.get_value("Sales Invoice", doc.name, "workflow_state") if doc.name else None

        if db_state != "Pending Debit Note Approval":
            frappe.throw(
                "Sales Invoice Return (B2B) with missing Customer Debit Note details "
                "requires approval. Please submit for approval or provide Debit Note details.",
                frappe.ValidationError
            )

        # Enforce that only the approver role (or Administrator) can submit it
        user_roles = frappe.get_roles(frappe.session.user)
        if approver_role not in user_roles and frappe.session.user != "Administrator":
            frappe.throw(
                f"Only users with the '{approver_role}' role can approve and submit "
                "this Sales Invoice Return.",
                frappe.PermissionError
            )


def populate_workflow_fields(doc):
    """
    Determines if the customer is B2B and whether the debit note details are complete.
    Populates:
      - custom_is_b2b_customer: 1 if customer has GSTIN, 0 otherwise
      - custom_debit_note_complete: 1 if debit note fields are complete, 0 otherwise
    """
    # 1. Check if the Customer is B2B (has GSTIN)
    if doc.customer:
        gstin = frappe.db.get_value("Customer", doc.customer, "gstin")
        doc.custom_is_b2b_customer = 1 if gstin else 0
    else:
        doc.custom_is_b2b_customer = 0

    # 2. Check if all three Debit Note fields are completed
    fields_filled = (
        bool(doc.custom_customer_debit_note_no) and
        bool(doc.custom_debit_note_date) and
        bool(doc.custom_debit_note_attachment)
    )
    doc.custom_debit_note_complete = 1 if fields_filled else 0

@frappe.whitelist()
def handle_recorrection(docname, correction_message):
    if not correction_message:
        frappe.throw("Correction Message is required", frappe.ValidationError)

    doc = frappe.get_doc("Sales Invoice", docname)

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

    # 2. Automatically create a Comment on the same Sales Invoice
    current_user_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    comment_text = f"Correction Requested\n\nRequested By:\n{current_user_name}\n\nReason:\n{correction_message}"
    doc.add_comment(
        comment_type="Comment",
        text=comment_text
    )

    # 3. Send Raven notification to the document creator (doc.owner)
    from workflow_manager.utils.notifications import send_raven_notification
    notification_message = (
        f"Your Sales Invoice {doc.name} has been sent back for correction.\n\n"
        f"Reason:\n{correction_message}"
    )
    send_raven_notification(
        recipient=doc.owner,
        message=notification_message,
        link_doctype="Sales Invoice",
        link_document=doc.name
    )

    return {"status": "success"}

