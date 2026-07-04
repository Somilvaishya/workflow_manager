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

    if doc.is_return == 1 and doc.custom_is_b2b_customer == 1 and doc.custom_debit_note_complete == 0:
        # Check database value of the workflow state to see what it was before transition
        db_state = frappe.db.get_value("Sales Invoice", doc.name, "workflow_state") if doc.name else None
        
        if db_state != "Pending Debit Note Approval":
            frappe.throw(
                "Sales Invoice Return (B2B) with missing Customer Debit Note details "
                "requires approval. Please submit for approval or provide Debit Note details.",
                frappe.ValidationError
            )
        
        # Enforce that only a user with the Accounts Approver role (or Administrator) can submit it
        user_roles = frappe.get_roles(frappe.session.user)
        if "Accounts Approver" not in user_roles and frappe.session.user != "Administrator":
            frappe.throw(
                "Only users with the Accounts Approver role can approve and submit "
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
