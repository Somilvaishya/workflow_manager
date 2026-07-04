import importlib
import frappe

def get_handler(doctype):
    """
    Dynamically loads and returns the handler module for a given DocType.
    Converts "Sales Invoice" -> "sales_invoice".
    """
    module_name = doctype.lower().replace(" ", "_")
    try:
        # Dynamically import the handler module
        module = importlib.import_module(f"workflow_manager.handlers.{module_name}")
        return module
    except ImportError:
        # Silently ignore if no handler exists for this DocType
        return None

def validate(doc, method=None):
    """
    Event hook for 'validate'.
    """
    handler = get_handler(doc.doctype)
    if handler and hasattr(handler, "validate"):
        handler.validate(doc)

def before_save(doc, method=None):
    """
    Event hook for 'before_save'.
    """
    handler = get_handler(doc.doctype)
    if handler and hasattr(handler, "before_save"):
        handler.before_save(doc)

def before_submit(doc, method=None):
    """
    Event hook for 'before_submit'.
    """
    handler = get_handler(doc.doctype)
    if handler and hasattr(handler, "before_submit"):
        handler.before_submit(doc)
