import importlib
import frappe

def get_handler(doctype):
    """
    Dynamically loads and returns the handler module for a given DocType.
    Converts "Sales Invoice" -> "sales_invoice".
    """
    module_name = doctype.lower().replace(" ", "_")
    try:
        # Dynamically import the handler module
        module = importlib.import_module(f"workflow_manager.handlers.{module_name}")
        return module
    except ImportError:
        # Silently ignore if no handler exists for this DocType
        return None

def validate(doc, method=None):
    """
    Event hook for 'validate'.
    """
    handler = get_handler(doc.doctype)
    if handler and hasattr(handler, "validate"):
        handler.validate(doc)

def before_save(doc, method=None):
    """
    Event hook for 'before_save'.
    """
    handler = get_handler(doc.doctype)
    if handler and hasattr(handler, "before_save"):
        handler.before_save(doc)

    # Centralized Raven notifications for workflow transitions
    send_workflow_state_notifications(doc)

def before_submit(doc, method=None):
    """
    Event hook for 'before_submit'.
    """
    handler = get_handler(doc.doctype)
    if handler and hasattr(handler, "before_submit"):
        handler.before_submit(doc)

def send_workflow_state_notifications(doc):
    """
    Sends Raven notifications to both the document creator (owner)
    and the approval role members on workflow state transitions.
    """
    if not doc.name or not doc.get("workflow_state"):
        return

    # Get the state before this save
    old_doc = doc.get_doc_before_save()
    old_state = old_doc.get("workflow_state") if old_doc else None
    new_state = doc.workflow_state

    # If the workflow state hasn't changed, do nothing
    if old_state == new_state:
        return

    from workflow_manager.utils.notifications import send_raven_notification

    # Fetch dynamic approver role from settings
    settings = frappe.get_single("Workflow Settings")
    approver_role = settings.approver_role or "Accounts Approver"

    # Fetch users with the approver role
    def get_approvers():
        users = frappe.get_all("Has Role", filters={"role": approver_role, "parenttype": "User"}, pluck="parent")
        if users:
            return frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="name")
        return []

    approvers = get_approvers()

    # Define state categories
    approval_states = ["Pending Approval", "Pending Debit Note Approval"]
    approved_states = ["Approved", "Submitted"]
    reject_states = ["Rejected", "Cancelled"]
    fix_states = ["Pending Fix"]

    creator_msg = None
    approver_msg = None

    if new_state in approval_states:
        creator_msg = f"Your {doc.doctype} *{doc.name}* has been submitted and is pending approval."
        approver_msg = f"A {doc.doctype} *{doc.name}* has been submitted by {doc.owner} and is pending your approval."
    elif new_state in approved_states:
        if old_state in approval_states:
            # Skip creator message for Journal Entry (handled in journal_entry.py before_save)
            if not (doc.doctype == "Journal Entry" and new_state == "Approved"):
                creator_msg = f"Your {doc.doctype} *{doc.name}* has been approved."
            approver_msg = f"The {doc.doctype} *{doc.name}* has been approved by {frappe.session.user}."
    elif new_state in reject_states:
        if old_state in approval_states:
            # Skip creator message for Journal Entry (handled in journal_entry.py before_save)
            if not (doc.doctype == "Journal Entry" and new_state == "Cancelled"):
                creator_msg = f"Your {doc.doctype} *{doc.name}* has been rejected."
            approver_msg = f"The {doc.doctype} *{doc.name}* has been rejected by {frappe.session.user}."
    elif new_state in fix_states:
        if old_state in approval_states:
            # Skip creator message as it's already sent by handle_recorrection with specific reason/remarks
            approver_msg = f"The {doc.doctype} *{doc.name}* has been sent back for correction."

    # Send message to creator (doc.owner)
    if creator_msg and doc.owner:
        try:
            send_raven_notification(
                recipient=doc.owner,
                message=creator_msg,
                link_doctype=doc.doctype,
                link_document=doc.name
            )
        except Exception as e:
            frappe.log_error(f"Error sending workflow creator notification: {e}", "Workflow Manager")

    # Send message to all users in the approver role
    if approver_msg and approvers:
        for appr in approvers:
            # Don't notify the user who triggered the transition
            if appr == frappe.session.user:
                continue
            try:
                send_raven_notification(
                    recipient=appr,
                    message=approver_msg,
                    link_doctype=doc.doctype,
                    link_document=doc.name
                )
            except Exception as e:
                frappe.log_error(f"Error sending workflow approver notification to {appr}: {e}", "Workflow Manager")
