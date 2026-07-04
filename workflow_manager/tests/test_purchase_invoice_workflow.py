import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

class TestPurchaseInvoiceWorkflow(FrappeTestCase):
    def setUp(self):
        # Mock password decryption to avoid site encryption key mismatches
        self.password_patcher = patch('frappe.utils.password.get_decrypted_password', return_value="dummy_secret")
        self.password_patcher.start()

        # Set up test suppliers and capture their actual names (keys)
        internal_name = "Test Internal Supplier"
        external_name = "Test External Supplier"

        if not frappe.db.exists("Supplier", {"supplier_name": internal_name}):
            sup = frappe.new_doc("Supplier")
            sup.supplier_name = internal_name
            sup.supplier_group = "Local"
            sup.custom_msme_registered = "No"
            sup.is_bns_internal_supplier = 1
            sup.insert(ignore_permissions=True)
            self.internal_supplier = sup.name
        else:
            self.internal_supplier = frappe.db.get_value("Supplier", {"supplier_name": internal_name}, "name")
            frappe.db.set_value("Supplier", self.internal_supplier, "is_bns_internal_supplier", 1)

        if not frappe.db.exists("Supplier", {"supplier_name": external_name}):
            sup = frappe.new_doc("Supplier")
            sup.supplier_name = external_name
            sup.supplier_group = "Local"
            sup.custom_msme_registered = "No"
            sup.is_bns_internal_supplier = 0
            sup.insert(ignore_permissions=True)
            self.external_supplier = sup.name
        else:
            self.external_supplier = frappe.db.get_value("Supplier", {"supplier_name": external_name}, "name")
            frappe.db.set_value("Supplier", self.external_supplier, "is_bns_internal_supplier", 0)

        # Ensure demo user exists
        if not frappe.db.exists("User", "demo@example.com"):
            user = frappe.new_doc("User")
            user.email = "demo@example.com"
            user.first_name = "Demo User"
            user.insert(ignore_permissions=True)

        # Enable workflow settings by default for workflow-specific tests
        settings = frappe.get_single("Workflow Settings")
        settings.enable_purchase_invoice_approval_workflow = 1
        settings.save(ignore_permissions=True)

        # Ensure we start as Administrator
        frappe.set_user("Administrator")

    def tearDown(self):
        self.password_patcher.stop()
        frappe.set_user("Administrator")

    def test_disabled_workflow_settings(self):
        # Disable workflow settings
        settings = frappe.get_single("Workflow Settings")
        settings.enable_purchase_invoice_approval_workflow = 0
        settings.save(ignore_permissions=True)

        # Create a Purchase Invoice (should not populate workflow fields)
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = self.external_supplier
        pi.location = "Gurukul, Faridabad"
        pi.company_gstin = "06AAJCK9474A1ZF"
        pi.place_of_supply = "06-Haryana"
        pi.bill_no = "BILL-100"
        pi.bill_date = "2026-07-04"
        pi.update_stock = 1
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "expense_account": "Stock In Hand - KGOPL",
            "warehouse": "Purchase Area - Gurukul HR - KGOPL"
        })
        pi.save(ignore_permissions=True)

        # Check fields are 0/empty
        self.assertEqual(pi.custom_wf_processed, 0)
        self.assertEqual(pi.custom_wf_pending_approval, 0)

    def test_external_supplier_items_without_po(self):
        # Case A: External supplier + no PO -> Should require approval
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = self.external_supplier
        pi.location = "Gurukul, Faridabad"
        pi.company_gstin = "06AAJCK9474A1ZF"
        pi.place_of_supply = "06-Haryana"
        pi.bill_no = "BILL-200"
        pi.bill_date = "2026-07-04"
        pi.update_stock = 1
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "expense_account": "Stock In Hand - KGOPL",
            "warehouse": "Purchase Area - Gurukul HR - KGOPL"
        })
        pi.save(ignore_permissions=True)

        # Verify computed flags
        self.assertEqual(pi.custom_wf_flag_1, 1)  # has items without PO
        self.assertEqual(pi.custom_wf_flag_2, 0)  # has items with PO
        self.assertEqual(pi.custom_wf_flag_3, 0)  # is internal supplier
        self.assertEqual(pi.custom_wf_pending_approval, 1)
        self.assertEqual(pi.custom_wf_direct_submit, 0)
        self.assertEqual(pi.custom_wf_processed, 1)

        # Direct submit should fail
        with self.assertRaises(frappe.ValidationError):
            pi.submit()

        # Apply workflow transition "Submit for Approval"
        from frappe.model.workflow import apply_workflow
        apply_workflow(pi, "Submit for Approval")
        self.assertEqual(pi.workflow_state, "Pending Approval")
        self.assertEqual(pi.docstatus, 0)

        # Test role check on submit (demo user does not have Accounts Manager role)
        frappe.set_user("demo@example.com")
        from frappe.model.workflow import WorkflowTransitionError
        with self.assertRaises((frappe.PermissionError, WorkflowTransitionError)):
            apply_workflow(pi, "Approve")

        # Approve and Submit as Accounts Manager/Administrator
        frappe.set_user("Administrator")
        apply_workflow(pi, "Approve")
        self.assertEqual(pi.workflow_state, "Approved")
        
        apply_workflow(pi, "Submit")
        self.assertEqual(pi.workflow_state, "Submitted")
        self.assertEqual(pi.docstatus, 1)

    def test_external_supplier_items_with_po(self):
        # Case B: External supplier + items with PO -> Direct submit allowed
        # Fetch an existing PO to bypass Supplier validation
        po_name = "PO060827-0125"
        po_supplier = frappe.db.get_value("Purchase Order", po_name, "supplier")
        
        # Ensure the PO supplier is external
        frappe.db.set_value("Supplier", po_supplier, "is_bns_internal_supplier", 0)

        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = po_supplier
        pi.location = "Gurukul, Faridabad"
        pi.company_gstin = "06AAJCK9474A1ZF"
        pi.place_of_supply = "06-Haryana"
        pi.bill_no = "BILL-300"
        pi.bill_date = "2026-07-04"
        pi.update_stock = 1
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "expense_account": "Stock In Hand - KGOPL",
            "warehouse": "Purchase Area - Gurukul HR - KGOPL",
            "purchase_order": po_name
        })
        pi.save(ignore_permissions=True)

        # Verify computed flags
        self.assertEqual(pi.custom_wf_flag_1, 0)  # has items without PO
        self.assertEqual(pi.custom_wf_flag_2, 1)  # has items with PO
        self.assertEqual(pi.custom_wf_flag_3, 0)  # is internal supplier
        self.assertEqual(pi.custom_wf_pending_approval, 0)
        self.assertEqual(pi.custom_wf_direct_submit, 1)

        # Direct submit via workflow "Submit"
        from frappe.model.workflow import apply_workflow
        apply_workflow(pi, "Submit")
        self.assertEqual(pi.workflow_state, "Submitted")
        self.assertEqual(pi.docstatus, 1)

    def test_internal_supplier_items_without_po(self):
        # Case C: Internal supplier + no PO -> Direct submit allowed (bypasses PO requirement)
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = self.internal_supplier
        pi.location = "Gurukul, Faridabad"
        pi.company_gstin = "06AAJCK9474A1ZF"
        pi.place_of_supply = "06-Haryana"
        pi.bill_no = "BILL-400"
        pi.bill_date = "2026-07-04"
        pi.update_stock = 1
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "expense_account": "Stock In Hand - KGOPL",
            "warehouse": "Purchase Area - Gurukul HR - KGOPL"
        })
        pi.save(ignore_permissions=True)

        # Verify computed flags
        self.assertEqual(pi.custom_wf_flag_1, 1)  # has items without PO
        self.assertEqual(pi.custom_wf_flag_2, 0)  # has items with PO
        self.assertEqual(pi.custom_wf_flag_3, 1)  # is internal supplier
        self.assertEqual(pi.custom_wf_pending_approval, 0)
        self.assertEqual(pi.custom_wf_direct_submit, 1)

        # Direct submit via workflow "Submit"
        from frappe.model.workflow import apply_workflow
        apply_workflow(pi, "Submit")
        self.assertEqual(pi.workflow_state, "Submitted")
        self.assertEqual(pi.docstatus, 1)
