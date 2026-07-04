import frappe

def validate(doc):
    """
    Validation logic for Purchase Invoice.
    """
    populate_workflow_fields(doc)

def before_save(doc):
    """
    Pre-save logic for Purchase Invoice.
    """
    populate_workflow_fields(doc)

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

    # If approval is required, ensure it was approved prior to submission
    if doc.custom_wf_pending_approval == 1:
        db_state = frappe.db.get_value("Purchase Invoice", doc.name, "workflow_state") if doc.name else None
        if db_state != "Approved":
            frappe.throw(
                "Purchase Invoice requires approval because it contains items without a Purchase Order. "
                "Please submit for approval before submitting.",
                frappe.ValidationError
            )

    # Enforce role restriction on submit (must be Accounts Manager or Administrator)
    user_roles = frappe.get_roles(frappe.session.user)
    if "Accounts Manager" not in user_roles and frappe.session.user != "Administrator":
        frappe.throw(
            "Only users with the Accounts Manager role can submit this Purchase Invoice.",
            frappe.PermissionError
        )

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
