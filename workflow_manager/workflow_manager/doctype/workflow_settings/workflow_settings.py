import frappe
from frappe.model.document import Document


WORKFLOW_MAP = {
    "enable_sales_invoice_approval_workflow": "Sales Invoice Return Workflow",
    "enable_purchase_invoice_approval_workflow": "Purchase Invoice Approval",
    "enable_journal_entry_approval_workflow": "Journal Entry Approval Workflow",
}


class WorkflowSettings(Document):
    def on_update(self):
        """
        Called whenever Workflow Settings is saved.
        1. Recreates all active workflows using the current approver_role — so any role
           change takes effect immediately across all transitions.
        2. Toggles is_active on each workflow document based on the enable checkboxes.
        3. Clears Frappe cache so changes are visible without a server restart.
        """
        approver_role = self.approver_role or "Accounts Approver"
        normal_role = self.normal_role or "All"

        from workflow_manager.setup.workflow import (
            setup_sales_invoice_workflow,
            setup_purchase_invoice_workflow,
            setup_journal_entry_workflow,
        )

        # Recreate workflows that are enabled (apply new roles + ensure correct transitions)
        if self.enable_sales_invoice_approval_workflow:
            setup_sales_invoice_workflow(approver_role, normal_role)
        if self.enable_purchase_invoice_approval_workflow:
            setup_purchase_invoice_workflow(approver_role, normal_role)
        if self.enable_journal_entry_approval_workflow:
            setup_journal_entry_workflow(approver_role, normal_role)

        # Toggle is_active for all workflows based on enable checkboxes
        for field, workflow_name in WORKFLOW_MAP.items():
            self._toggle_workflow(workflow_name, self.get(field))

        frappe.clear_cache()

    def _toggle_workflow(self, workflow_name: str, enabled) -> None:
        if not frappe.db.exists("Workflow", workflow_name):
            return
        is_active = 1 if enabled else 0
        current = frappe.db.get_value("Workflow", workflow_name, "is_active")
        if current != is_active:
            frappe.db.set_value("Workflow", workflow_name, "is_active", is_active)
