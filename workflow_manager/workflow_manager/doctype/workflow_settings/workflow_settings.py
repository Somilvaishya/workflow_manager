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
        Whenever the Workflow Settings doc is saved, sync the is_active flag
        on each corresponding Frappe Workflow document and clear cache so the
        change takes effect immediately without a server restart.
        """
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
