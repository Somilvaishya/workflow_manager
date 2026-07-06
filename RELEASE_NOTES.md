# Release Notes - Workflow Manager v1.2.0

We are pleased to announce the release of **Workflow Manager v1.2.0**. This release introduces enhancements to the Sales Invoice Return Workflow (replacing Reject with Pending Recorrection) and a redesigned, collapsible UI layout for Customer Debit Notes on Sales Invoices.

---

## 🚀 New Features & Enhancements

### 1. Sales Invoice Return Workflow Enhancements
*   **Pending Recorrection Transition**: Replaced the previous `Reject` transition with `Pending Recorrection`, routing the workflow to the `Pending Fix` state.
*   **Remarks Prompt**: Intercepts the transition on the client side, prompting the approver for a mandatory `Correction Message` before permitting state changes.
*   **Timeline Comments**: Automatically logs a Timeline Comment tracking the correction message, requester, and timestamp.
*   **Raven Integration**: Dispatches direct chat messages to the Sales Invoice owner (`doc.owner`) containing the correction reasons and links.
*   **Role Enforcement**: Secures backend transitions by validating that only users with the `Accounts Approver` role can initiate the recorrection.

### 2. Redesigned Customer Debit Note UI
*   **Collapsible Section**: Provisions a new collapsible `"Customer Debit Note Details"` section on the Sales Invoice layout.
*   **Visibility Bounds**: Automatically displays the section only when `doc.is_return == 1` (remains hidden for regular Sales Invoices).
*   **Responsive 2-Column Grid**: Organized fields cleanly using Column Breaks:
    *   **Left Column**: `Customer Debit Note No` and `Debit Note Attachment`.
    *   **Right Column**: `Debit Note Date`.
*   **Accounting Dimensions Cleanup**: Moved these fields out of Accounting Dimensions to present a cleaner interface.

---

## 🧪 Testing & Verification
*   Added unit tests to `test_sales_invoice_workflow.py` asserting role permission checks, remarks dialog triggers, empty validation checks, comment writing, Raven notification delivery, and transitions from `Pending Fix` back to `Pending Debit Note Approval` or `Submitted`.
*   **All 11 tests executed and passed successfully.**
