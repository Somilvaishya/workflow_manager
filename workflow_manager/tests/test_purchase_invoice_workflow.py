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

        # Run custom field setup to make sure fields are provisioned
        from workflow_manager.setup.custom_fields import setup_custom_fields
        setup_custom_fields()

        # Ensure Administrator has a Raven User profile
        if not frappe.db.exists("Raven User", {"user": "Administrator"}):
            ru = frappe.new_doc("Raven User")
            ru.user = "Administrator"
            ru.full_name = "Administrator"
            ru.insert(ignore_permissions=True)

        # Ensure Accounts Bot exists
        if not frappe.db.exists("Raven Bot", "Accounts Bot"):
            if not frappe.db.exists("Raven User", "accounts_bot"):
                ru = frappe.new_doc("Raven User")
                ru.name = "accounts_bot"
                ru.full_name = "Accounts Bot User"
                ru.insert(ignore_permissions=True)
            bot = frappe.new_doc("Raven Bot")
            bot.bot_name = "Accounts Bot"
            bot.raven_user = "accounts_bot"
            bot.insert(ignore_permissions=True)


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

    def test_recorrection_workflow(self):
        # Create a Purchase Invoice that goes to Pending Approval
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = self.external_supplier
        pi.location = "Gurukul, Faridabad"
        pi.company_gstin = "06AAJCK9474A1ZF"
        pi.place_of_supply = "06-Haryana"
        pi.bill_no = "BILL-500"
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

        # Transition to Pending Approval first
        from frappe.model.workflow import apply_workflow
        apply_workflow(pi, "Submit for Approval")
        self.assertEqual(pi.workflow_state, "Pending Approval")

        # 1. Test empty correction message raises exception
        from workflow_manager.handlers.purchase_invoice import handle_recorrection
        with self.assertRaises(frappe.ValidationError):
            handle_recorrection(pi.name, "")

        # 2. Test unauthorized user permission check
        frappe.set_user("demo@example.com")
        with self.assertRaises(frappe.PermissionError):
            handle_recorrection(pi.name, "Need to link PO")

        # 3. Transition to Pending Fix as Administrator (who has Accounts Manager role)
        frappe.set_user("Administrator")
        res = handle_recorrection(pi.name, "Please fix the rates")
        self.assertEqual(res.get("status"), "success")

        # Verify workflow state changed
        pi.reload()
        self.assertEqual(pi.workflow_state, "Pending Fix")

        # Verify Comment is created in database
        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Purchase Invoice", "reference_name": pi.name},
            fields=["content"]
        )
        self.assertTrue(any("Please fix the rates" in c.content for c in comments))

        # Verify Raven message was sent/inserted
        messages = frappe.get_all(
            "Raven Message",
            filters={"link_doctype": "Purchase Invoice", "link_document": pi.name},
            fields=["text"]
        )
        self.assertTrue(any("Please fix the rates" in m.text for m in messages))

    def test_purchase_receipt_mapping_single(self):
        # 1. Create a Purchase Receipt with supplier invoice fields populated
        pr = frappe.new_doc("Purchase Receipt")
        pr.company = "K.G. Overseas Private Limited"
        pr.supplier = self.external_supplier
        pr.location = "Gurukul, Faridabad"
        pr.posting_date = "2026-07-04"
        pr.bill_no = "INV-PR-999"
        pr.bill_date = "2026-07-04"
        pr.bns_ewaybill_date = "2026-07-04"
        pr.bns_ewaybill_attachment = "/private/files/ewaybill.pdf"
        pr.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "warehouse": "Purchase Area - Gurukul HR - KGOPL"
        })
        pr.save(ignore_permissions=True)
        pr.submit()

        # 2. Create a Purchase Invoice referencing this Purchase Receipt
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = self.external_supplier
        pi.location = "Gurukul, Faridabad"
        pi.posting_date = "2026-07-04"
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "purchase_receipt": pr.name,
            "pr_detail": pr.items[0].name,
            "warehouse": "Purchase Area - Gurukul HR - KGOPL",
            "expense_account": "Stock In Hand - KGOPL"
        })

        # Save triggers validate/before_save which calls our mapper
        pi.save(ignore_permissions=True)

        # Verify fields are mapped correctly
        self.assertEqual(pi.bill_no, "INV-PR-999")
        self.assertEqual(pi.bill_date, frappe.utils.getdate("2026-07-04"))
        self.assertEqual(pi.bns_ewaybill_date, frappe.utils.getdate("2026-07-04"))
        self.assertEqual(pi.bns_ewaybill_attachment, "/private/files/ewaybill.pdf")


    def test_purchase_receipt_mapping_conflicting(self):
        # 1. Create PR 1
        pr1 = frappe.new_doc("Purchase Receipt")
        pr1.company = "K.G. Overseas Private Limited"
        pr1.supplier = self.external_supplier
        pr1.location = "Gurukul, Faridabad"
        pr1.posting_date = "2026-07-04"
        pr1.bill_no = "INV-CONF-1"
        pr1.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "warehouse": "Purchase Area - Gurukul HR - KGOPL"
        })
        pr1.save(ignore_permissions=True)
        pr1.submit()

        # 2. Create PR 2 with a different bill_no
        pr2 = frappe.new_doc("Purchase Receipt")
        pr2.company = "K.G. Overseas Private Limited"
        pr2.supplier = self.external_supplier
        pr2.location = "Gurukul, Faridabad"
        pr2.posting_date = "2026-07-04"
        pr2.bill_no = "INV-CONF-2"
        pr2.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "warehouse": "Purchase Area - Gurukul HR - KGOPL"
        })
        pr2.save(ignore_permissions=True)
        pr2.submit()

        # 3. Create a consolidated Purchase Invoice
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "K.G. Overseas Private Limited"
        pi.supplier = self.external_supplier
        pi.location = "Gurukul, Faridabad"
        pi.posting_date = "2026-07-04"
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "purchase_receipt": pr1.name,
            "pr_detail": pr1.items[0].name,
            "warehouse": "Purchase Area - Gurukul HR - KGOPL",
            "expense_account": "Stock In Hand - KGOPL"
        })
        pi.append("items", {
            "item_code": "P2381",
            "qty": 1.0,
            "rate": 285.0,
            "purchase_receipt": pr2.name,
            "pr_detail": pr2.items[0].name,
            "warehouse": "Purchase Area - Gurukul HR - KGOPL",
            "expense_account": "Stock In Hand - KGOPL"
        })

        # Save to trigger mapping
        pi.save(ignore_permissions=True)

        # Since bill_no conflicts, it should NOT be mapped
        self.assertFalse(pi.bill_no)



