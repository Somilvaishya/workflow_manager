# Release Notes - Workflow Manager v1.1.0

We are pleased to announce the release of **Workflow Manager v1.1.0**. This release introduces a reusable remarks dialog for workflow transitions, automated Raven notifications, and server-side mapping of supplier invoice details from Purchase Receipts to Purchase Invoices.

---

## 🚀 New Features & Enhancements

### 1. Purchase Invoice Correction Dialog
*   **Remarks Prompt**: Intercepts the **Pending Recorrection** workflow action on Purchase Invoices.
*   **Correction Dialog**: Opens a mandatory remarks dialog (`Correction Required`) requesting the user to input a `Correction Message` before transitioning the document state.
*   **Timeline Comments**: Automatically records the correction reason in the document timeline.
*   **Reusable Dialog Helper**: Implemented the client-side dialog under `window.workflow_manager.prompt_workflow_action_comment` to make it easily reusable by other workflow actions.

### 2. Reusable Raven Notification Utility
*   **Raven Integration**: Automatically dispatches a direct chat notification to the document owner (`doc.owner`) containing the Invoice Number, new State, and Correction Message.
*   **Automatic Provisioning**: Dynamically verifies and provisions the recipient's Raven User profile if they are not already registered in Raven, ensuring warning-free delivery.
*   **Generic Notification Helper**: Encapsulated in the `workflow_manager.utils.notifications` module for general reuse across other custom apps.

### 3. Purchase Receipt to Purchase Invoice Mapping
*   **Supplier Invoice Details**: Automatically copies `bill_no`, `bill_date`, `bns_ewaybill_date`, and `bns_ewaybill_attachment` fields from linked Purchase Receipts during Purchase Invoice creation.
*   **Collapsible UI Section**: Provisions a new collapsible `Supplier Invoice` section on the Purchase Receipt form to cleanly capture invoice information.
*   **Consolidation & Conflict Prevention**:
    *   If a Purchase Invoice consolidates multiple Purchase Receipts with identical invoice details, the details are safely mapped.
    *   If conflicting details are detected (e.g. different invoice numbers or dates), the fields are left blank for manual verification, and a mapping warning prompt is displayed to the user.
*   **Pure Server-Side Execution**: Implemented inside `validate` and `before_save` and guarded by `doc.is_new()`, making it completely consistent across Desk, APIs, and background integrations.

---

## 🧪 Testing & Verification
*   Added comprehensive backend unit tests covering the new workflow transition permission checks, empty comment validations, comment timeline recording, Raven message deliveries, single receipt mapping, and conflicting receipt consolidations.
*   **All 10 tests passed successfully.**
