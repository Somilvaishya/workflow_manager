import frappe
from frappe.model.document import Document

from workflow_manager.setup.workflow import sync_workflow_active_flags


class WorkflowSettings(Document):
    def on_update(self):
        """
        Called whenever Workflow Settings is saved.

        1. Rebuilds all three workflows from code when the approver/normal role
           changed, or when "Rebuild Workflows On Save" was ticked. A rebuild
           discards manual edits made in the Workflow UI, so it is never done for
           a plain enable/disable toggle.
        2. Keeps each workflow's is_active in step with its enable checkbox.
        3. Clears the cache so the change is visible without a server restart.
        """
        approver_role = self.approver_role or "Accounts Approver"
        normal_role = self.normal_role or "All"

        roles_changed = self.has_value_changed("approver_role") or self.has_value_changed(
            "normal_role"
        )
        # .get() so this still works on a site whose schema has not synced the field yet
        rebuild_requested = bool(self.get("rebuild_workflows"))

        if roles_changed or rebuild_requested:
            from workflow_manager.setup.workflow import (
                setup_journal_entry_workflow,
                setup_purchase_invoice_workflow,
                setup_sales_invoice_workflow,
            )

            # Rebuild all three (not just the enabled ones) so a disabled workflow
            # does not keep a stale role and surprise everyone when re-enabled.
            setup_sales_invoice_workflow(approver_role, normal_role, force=True)
            setup_purchase_invoice_workflow(approver_role, normal_role, force=True)
            setup_journal_entry_workflow(approver_role, normal_role, force=True)

        # Toggle is_active for all workflows based on the enable checkboxes
        sync_workflow_active_flags()

        if rebuild_requested:
            # One-shot switch: clear it so the next ordinary save is harmless.
            self.db_set("rebuild_workflows", 0, update_modified=False)

        frappe.clear_cache()
