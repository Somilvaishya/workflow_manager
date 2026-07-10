import frappe

def validate(doc):
    """
    Validation logic for Journal Entry.
    """
    populate_workflow_fields(doc)

def before_save(doc):
    """
    Pre-save logic for Journal Entry. Detects workflow transitions to notify user.
    """
    # Detect transitions before updating fields
    if doc.name:
        db_state = frappe.db.get_value("Journal Entry", doc.name, "workflow_state")
        if db_state and doc.workflow_state != db_state:
            from workflow_manager.utils.notifications import send_raven_notification
            
            if doc.workflow_state == "Approved":
                send_raven_notification(
                    recipient=doc.owner,
                    message=f"Your Journal Entry {doc.name} has been Approved by Accounts Approver.",
                    link_doctype="Journal Entry",
                    link_document=doc.name
                )
            elif doc.workflow_state == "Cancelled":
                send_raven_notification(
                    recipient=doc.owner,
                    message=f"Your Journal Entry {doc.name} has been Rejected by Accounts Approver.",
                    link_doctype="Journal Entry",
                    link_document=doc.name
                )

    populate_workflow_fields(doc)

def before_submit(doc):
    """
    Submission validation for Journal Entry.
    """
    populate_workflow_fields(doc)

    settings = frappe.get_single("Workflow Settings")
    if not settings.enable_journal_entry_approval_workflow:
        return

    # If approval is required, ensure it was approved prior to submission
    if doc.custom_je_pending_approval == 1:
        db_state = frappe.db.get_value("Journal Entry", doc.name, "workflow_state") if doc.name else None
        if db_state != "Approved":
            frappe.throw(
                "Journal Entry requires approval because it debits from a Suspense Account. "
                "Please submit for approval before submitting.",
                frappe.ValidationError
            )

    # Enforce role restriction on submit (must be Accounts Approver or Administrator)
    user_roles = frappe.get_roles(frappe.session.user)
    if "Accounts Approver" not in user_roles and frappe.session.user != "Administrator":
        frappe.throw(
            "Only users with the Accounts Approver role can submit this Journal Entry.",
            frappe.PermissionError
        )

def populate_workflow_fields(doc):
    """
    Evaluates if the Journal Entry debits from any suspense account.
    """
    settings = frappe.get_single("Workflow Settings")
    if not settings.enable_journal_entry_approval_workflow:
        doc.custom_je_pending_approval = 0
        return

    has_suspense_debit = False
    if doc.accounts:
        for acc_row in doc.accounts:
            if acc_row.debit > 0 and acc_row.account:
                is_suspense = frappe.db.get_value("Account", acc_row.account, "bns_suspense_account")
                if is_suspense:
                    has_suspense_debit = True
                    break

    doc.custom_je_pending_approval = 1 if has_suspense_debit else 0

@frappe.whitelist()
def handle_recorrection(docname, correction_message):
    if not correction_message:
        frappe.throw("Correction Message is required", frappe.ValidationError)

    doc = frappe.get_doc("Journal Entry", docname)

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

    # 2. Automatically create a Comment on the same Journal Entry
    comment_text = f"Correction requested by Accounts Approver.\n\nReason:\n{correction_message}"
    doc.add_comment(
        comment_type="Comment",
        text=comment_text
    )

    # 3. Send Raven notification to the document creator (doc.owner)
    from workflow_manager.utils.notifications import send_raven_notification
    notification_message = (
        f"Your Journal Entry {doc.name} has been sent back for correction.\n\n"
        f"Reason:\n{correction_message}"
    )
    send_raven_notification(
        recipient=doc.owner,
        message=notification_message,
        link_doctype="Journal Entry",
        link_document=doc.name
    )

    return {"status": "success"}
