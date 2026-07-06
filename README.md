# Workflow Manager

A generic, upgrade-safe, and reusable Frappe/ERPNext application extending core document workflows and UI interfaces without modifying core files.

---

## 🚀 Key Features

### 1. Purchase Invoice Approval Workflow
*   **Approval & Submission Routing**: Dynamic routing based on B2B suppliers, PO presence, and internal/external partner classifications.
*   **Correction Dialog ("Pending Recorrection")**: Intercepts the transition on the client side to prompt the approver for a mandatory `Correction Message` before transitioning state to `Pending Fix`.
*   **Automated Timeline Log**: Automatically inserts a detailed comment into the invoice timeline.
*   **Raven Direct Message**: Dispatches direct chat messages to the invoice creator via a secure Raven Bot, automatically verifying and provisioning Raven User profiles if needed.

### 2. Sales Invoice Return Workflow
*   **Interactive Recorrection Transition**: Replaced the native `Reject` transition in the return workflow with `Pending Recorrection` routing to `Pending Fix` state.
*   **Modular Reusability**: Reuses the global remarks dialog prompt and Raven notification helper, ensuring clean code separation.
*   **Accounts Approver Security**: Validates permissions on the server side to ensure only authorized users can initiate recorrection actions.

### 3. Customer Debit Note UI Redesign
*   **Collapsible section**: Added a new `"Customer Debit Note Details"` section on the Sales Invoice form.
*   **Conditional Visibility**: Dynamically displays the section only when `doc.is_return == 1` (hidden for normal Sales Invoices).
*   **Responsive Grid**: Arranged fields in a clean 2-column layout:
    *   **Left Column**: `Customer Debit Note No` and `Debit Note Attachment`.
    *   **Right Column**: `Debit Note Date`.

### 4. Purchase Receipt to Purchase Invoice Mapper
*   **Server-Side Mapping**: Automatically copies `bill_no`, `bill_date`, `bns_ewaybill_date`, and `bns_ewaybill_attachment` from linked Purchase Receipts to Purchase Invoices on creation.
*   **Consolidation & Conflict Resolution**:
    *   Aggregates fields if all referenced receipts have identical information.
    *   If details conflict across receipts, keeps fields blank for manual entry and presents a mapping warning to the user.

---

## 🛠️ Reusable Architecture
*   **Global Client-Side Helper**: `window.workflow_manager.prompt_workflow_action_comment` ([workflow_utils.js](workflow_manager/public/js/workflow_utils.js)) implements remarks capture dynamically.
*   **Raven Notification Utility**: `workflow_manager.utils.notifications.send_raven_notification` ([notifications.py](workflow_manager/utils/notifications.py)) is reusable globally by other apps.
*   **Document Mapping Service**: `workflow_manager.mappers.purchase_receipt` ([purchase_receipt.py](workflow_manager/mappers/purchase_receipt.py)) separates business mapping logic from document handlers.

---

## 🧪 Testing & Verification
The application includes extensive unit tests checking roles, permissions, comment creation, Raven integration, receipt mapping, and layout visibility.

To run the automated test suite:
```bash
bench --site [your-site-name] run-tests --app workflow_manager
```

---

## 📦 Installation
Install this application using the [bench](https://github.com/frappe/bench) CLI:
```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/Somilvaishya/workflow_manager.git
bench install-app workflow_manager
```

## 📄 License
MIT
