import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

class TestSalesInvoiceWorkflow(FrappeTestCase):
    def setUp(self):
        # Mock get_decrypted_password to bypass encryption key mismatch issues on test environment
        self.password_patcher = patch('frappe.utils.password.get_decrypted_password', return_value="dummy_secret")
        self.password_patcher.start()

        self.b2b_customer = "C2607-02"
        self.b2c_customer = "C1136"
        
        if not frappe.db.exists("Customer", self.b2b_customer):
            customers = frappe.get_all("Customer", filters={"gstin": ["is", "set"]}, limit=1)
            if customers:
                self.b2b_customer = customers[0].name
            else:
                import random
                rand_num = random.randint(1000, 9999)
                cust = frappe.new_doc("Customer")
                cust.customer_name = f"Test B2B Customer {rand_num}"
                cust.customer_group = "Individual"
                cust.territory = "India"
                cust.gstin = f"07CCQPJ{rand_num}N1ZE" # Valid-like structure
                cust.insert(ignore_permissions=True)
                self.b2b_customer = cust.name
            
            # Ensure the selected or created B2B customer has a valid GSTIN
            frappe.db.set_value("Customer", self.b2b_customer, "gstin", "07CCQPJ9999N1ZE")

        if not frappe.db.exists("Customer", self.b2c_customer):
            customers = frappe.get_all("Customer", filters={"gstin": ["is", "not", "set"]}, limit=1)
            if customers:
                self.b2c_customer = customers[0].name
            else:
                cust = frappe.new_doc("Customer")
                cust.customer_name = "Test B2C Customer"
                cust.customer_group = "Individual"
                cust.territory = "India"
                cust.gstin = ""
                cust.insert(ignore_permissions=True)
                self.b2c_customer = cust.name

        # Ensure demo user exists
        if not frappe.db.exists("User", "demo@example.com"):
            user = frappe.new_doc("User")
            user.email = "demo@example.com"
            user.first_name = "Demo User"
            user.insert(ignore_permissions=True)
            
        # Ensure we start as Administrator
        frappe.set_user("Administrator")

        # Run custom field setup to make sure fields are provisioned
        from workflow_manager.setup.custom_fields import setup_custom_fields
        setup_custom_fields()

        # Run workflow setup to apply workflow changes
        from workflow_manager.setup.workflow import setup_workflow
        setup_workflow()

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
        
    def test_b2c_customer_return(self):
        # Return for B2C customer should NOT require debit note fields
        si = frappe.new_doc("Sales Invoice")
        si.company = "K.G. Overseas Private Limited"
        si.customer = self.b2c_customer
        si.debit_to = "Debtors - KGOPL"
        si.location = "KGOPL Kamla Nagar, Agra"
        si.company_gstin = "09AAJCK9474A1Z9"
        si.place_of_supply = "09-Uttar Pradesh"
        si.is_return = 1
        si.update_stock = 1
        si.append("items", {
            "item_code": "CS125",
            "qty": -1.0,
            "rate": 350.0,
            "income_account": "Sales - KGOPL",
            "warehouse": "Kamla Nagar, Agra - KGOPL"
        })
        si.save(ignore_permissions=True)
        
        # Verify custom fields are computed
        self.assertEqual(si.custom_is_b2b_customer, 0)
        self.assertEqual(si.custom_debit_note_complete, 0)
        
        # B2C return should allow submission directly via workflow action "Submit"
        from frappe.model.workflow import apply_workflow
        apply_workflow(si, "Submit")
        self.assertEqual(si.workflow_state, "Submitted")
        self.assertEqual(si.docstatus, 1)
 
    def test_b2b_customer_return_complete(self):
        # Return for B2B customer with all fields filled
        si = frappe.new_doc("Sales Invoice")
        si.company = "K.G. Overseas Private Limited"
        si.customer = self.b2b_customer
        si.debit_to = "Debtors - KGOPL"
        si.location = "KGOPL Kamla Nagar, Agra"
        si.company_gstin = "09AAJCK9474A1Z9"
        si.place_of_supply = "09-Uttar Pradesh"
        si.is_return = 1
        si.update_stock = 1
        si.custom_customer_debit_note_no = "DN-123"
        si.custom_debit_note_date = "2026-07-04"
        si.custom_debit_note_attachment = "/private/files/debit_note.pdf"
        si.append("items", {
            "item_code": "CS125",
            "qty": -1.0,
            "rate": 350.0,
            "income_account": "Sales - KGOPL",
            "warehouse": "Kamla Nagar, Agra - KGOPL"
        })
        si.save(ignore_permissions=True)
        
        # Verify custom fields are computed
        self.assertEqual(si.custom_is_b2b_customer, 1)
        self.assertEqual(si.custom_debit_note_complete, 1)
        
        # Should submit directly via transition "Submit" because custom_debit_note_complete == 1
        from frappe.model.workflow import apply_workflow
        apply_workflow(si, "Submit")
        self.assertEqual(si.workflow_state, "Submitted")
        self.assertEqual(si.docstatus, 1)
 
    def test_b2b_customer_return_incomplete_direct_submit_fails(self):
        # Return for B2B customer with missing fields
        si = frappe.new_doc("Sales Invoice")
        si.company = "K.G. Overseas Private Limited"
        si.customer = self.b2b_customer
        si.debit_to = "Debtors - KGOPL"
        si.location = "KGOPL Kamla Nagar, Agra"
        si.company_gstin = "09AAJCK9474A1Z9"
        si.place_of_supply = "09-Uttar Pradesh"
        si.is_return = 1
        si.update_stock = 1
        si.append("items", {
            "item_code": "CS125",
            "qty": -1.0,
            "rate": 350.0,
            "income_account": "Sales - KGOPL",
            "warehouse": "Kamla Nagar, Agra - KGOPL"
        })
        si.save(ignore_permissions=True)
        
        # Verify custom fields are computed
        self.assertEqual(si.custom_is_b2b_customer, 1)
        self.assertEqual(si.custom_debit_note_complete, 0)
        
        # Direct submit (bypassing workflow) should raise ValidationError
        with self.assertRaises(frappe.ValidationError):
            si.submit()
 
        # First transition it to Pending Debit Note Approval by calling workflow Submit
        from frappe.model.workflow import apply_workflow
        apply_workflow(si, "Submit")
        self.assertEqual(si.workflow_state, "Pending Debit Note Approval")
        self.assertEqual(si.docstatus, 0) # Still Draft/0
        
        # Switch user to demo user (who does not have Accounts Approver role)
        frappe.set_user("demo@example.com")
        
        # Should raise transition error (WorkflowTransitionError) since demo@example.com doesn't have the Accounts Approver role
        from frappe.model.workflow import WorkflowTransitionError
        with self.assertRaises((frappe.PermissionError, WorkflowTransitionError)):
            apply_workflow(si, "Approve")
            
        # Switch back to Administrator (who acts as superuser and has permission) and approve it
        frappe.set_user("Administrator")
        apply_workflow(si, "Approve")
        self.assertEqual(si.workflow_state, "Submitted")
        self.assertEqual(si.docstatus, 1)

    def test_recorrection_workflow(self):
        # Create an incomplete return invoice for B2B customer (goes to Pending Debit Note Approval)
        si = frappe.new_doc("Sales Invoice")
        si.company = "K.G. Overseas Private Limited"
        si.customer = self.b2b_customer
        si.debit_to = "Debtors - KGOPL"
        si.location = "KGOPL Kamla Nagar, Agra"
        si.company_gstin = "09AAJCK9474A1Z9"
        si.place_of_supply = "09-Uttar Pradesh"
        si.is_return = 1
        si.update_stock = 1
        si.append("items", {
            "item_code": "CS125",
            "qty": -1.0,
            "rate": 350.0,
            "income_account": "Sales - KGOPL",
            "warehouse": "Kamla Nagar, Agra - KGOPL"
        })
        si.save(ignore_permissions=True)

        # Transition it to Pending Debit Note Approval by calling workflow Submit
        from frappe.model.workflow import apply_workflow
        apply_workflow(si, "Submit")
        self.assertEqual(si.workflow_state, "Pending Debit Note Approval")

        # 1. Test empty correction message raises exception
        from workflow_manager.handlers.sales_invoice import handle_recorrection
        with self.assertRaises(frappe.ValidationError):
            handle_recorrection(si.name, "")

        # 2. Test unauthorized user permission check
        frappe.set_user("demo@example.com")
        with self.assertRaises(frappe.PermissionError):
            handle_recorrection(si.name, "Missing debit note")

        # 3. Transition to Pending Fix as Administrator (who has Accounts Approver role)
        frappe.set_user("Administrator")
        res = handle_recorrection(si.name, "Please attach scanned copy of debit note")
        self.assertEqual(res.get("status"), "success")

        # Verify workflow state changed to Pending Fix
        si.reload()
        self.assertEqual(si.workflow_state, "Pending Fix")

        # Verify Comment is created in database
        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Invoice", "reference_name": si.name},
            fields=["content"]
        )
        self.assertTrue(any("Please attach scanned copy of debit note" in c.content for c in comments))
        self.assertTrue(any("Correction Requested" in c.content for c in comments))

        # Verify Raven message was sent/inserted
        messages = frappe.get_all(
            "Raven Message",
            filters={"link_doctype": "Sales Invoice", "link_document": si.name},
            fields=["text"]
        )
        self.assertTrue(any("Please attach scanned copy of debit note" in m.text for m in messages))

        # 4. Save and Submit from Pending Fix
        # Fill in the debit note details
        si.custom_customer_debit_note_no = "DN-456"
        si.custom_debit_note_date = "2026-07-06"
        si.custom_debit_note_attachment = "/private/files/debit_note_fixed.pdf"
        si.save(ignore_permissions=True)

        # Submit should now transition directly to Submitted because complete is 1
        apply_workflow(si, "Submit")
        self.assertEqual(si.workflow_state, "Submitted")
        self.assertEqual(si.docstatus, 1)

