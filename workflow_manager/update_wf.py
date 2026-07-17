import frappe

def run():
    wf = frappe.get_doc("Workflow", "Purchase Invoice Approval")
    
    updated = False
    for t in wf.transitions:
        if t.state == "Submitted" and t.action == "Cancel" and t.next_state == "Cancelled":
            if t.allowed != "All":
                t.allowed = "All"
                updated = True
    
    if updated:
        wf.save()
        frappe.db.commit()
        print("Successfully updated Cancel transition allowed role to 'All'")
    else:
        print("No updates were necessary or transition not found.")
