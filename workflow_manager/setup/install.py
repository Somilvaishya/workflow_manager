import frappe
from workflow_manager.setup.custom_fields import setup_custom_fields
from workflow_manager.setup.workflow import setup_workflow

def after_install():
    print("Setting up custom fields...")
    setup_custom_fields()
    print("Setting up workflow...")
    setup_workflow()
    print("Workflow Manager setup complete.")
