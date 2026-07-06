app_name = "workflow_manager"
app_title = "Workflow Manager"
app_publisher = "Somil"
app_description = "Workflow Manager App"
app_email = "somil@example.com"
app_license = "mit"

# Document Events
# ---------------
doc_events = {
    "Sales Invoice": {
        "validate": "workflow_manager.router.validate",
        "before_save": "workflow_manager.router.before_save",
        "before_submit": "workflow_manager.router.before_submit"
    },
    "Purchase Invoice": {
        "validate": "workflow_manager.router.validate",
        "before_save": "workflow_manager.router.before_save",
        "before_submit": "workflow_manager.router.before_submit"
    }
}

# Client Scripts
# --------------
app_include_js = "/assets/workflow_manager/js/workflow_utils.js"

doctype_js = {
    "Sales Invoice": "public/js/sales_invoice.js",
    "Purchase Invoice": "public/js/purchase_invoice.js"
}


# Installation & Migration Hooks
# ------------------------------
after_install = "workflow_manager.setup.install.after_install"
after_migrate = "workflow_manager.setup.install.after_install"
