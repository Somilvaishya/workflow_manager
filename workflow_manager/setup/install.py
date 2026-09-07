from workflow_manager.setup.custom_fields import setup_custom_fields
from workflow_manager.setup.workflow import setup_workflow


def after_install():
    """Fresh install: build custom fields and workflows from scratch."""
    print("Setting up custom fields...")
    setup_custom_fields()
    print("Setting up workflow...")
    setup_workflow(force=True)
    print("Workflow Manager setup complete.")


def after_migrate():
    """
    Migrate: refresh custom fields, create only the workflows that are missing,
    and re-sync is_active with Workflow Settings.

    Workflows are deliberately NOT rebuilt here — doing so would wipe any tuning
    done in the Workflow UI on every `bench migrate`. Use the "Rebuild Workflows"
    checkbox in Workflow Settings to regenerate them from code.
    """
    setup_custom_fields()
    setup_workflow(force=False)
