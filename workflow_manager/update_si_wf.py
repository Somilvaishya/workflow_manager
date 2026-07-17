import frappe
import json

def run():
    wf_name = "Sales Invoice Approval Workflow" # Assuming standard naming convention
    
    # Try to find the exact workflow name if the guessed one doesn't exist
    if not frappe.db.exists("Workflow", wf_name):
        wfs = frappe.get_all("Workflow", filters={"document_type": "Sales Invoice", "is_active": 1}, pluck="name")
        if wfs:
            wf_name = wfs[0]
        else:
            print("No active Sales Invoice Workflow found!")
            return

    wf = frappe.get_doc("Workflow", wf_name)
    
    print(f"Modifying workflow: {wf_name}")
    
    updated = False
    
    # 1. Update Cancel transition to All
    for t in wf.transitions:
        if t.state == "Submitted" and t.action == "Cancel" and t.next_state == "Cancelled":
            if t.allowed != "All":
                print(f"Changing Cancel allowed from {t.allowed} to All")
                t.allowed = "All"
                updated = True
                
    # 2. Cleanup redundant Submit/Transitions (where All already exists for the same state/action/next_state/condition)
    to_remove = []
    seen = {}
    for t in wf.transitions:
        key = (t.state, t.action, t.next_state, t.condition)
        if key not in seen:
            seen[key] = []
        seen[key].append(t)
        
    for key, transitions in seen.items():
        if len(transitions) > 1:
            has_all = any(x.allowed == "All" for x in transitions)
            if has_all:
                for x in transitions:
                    if x.allowed != "All":
                        print(f"Removing redundant transition for role {x.allowed}: {key[0]} -> {key[2]} ({key[1]})")
                        to_remove.append(x)
                        
    for r in to_remove:
        wf.transitions.remove(r)
        updated = True
        
    if updated:
        wf.save()
        frappe.db.commit()
        print("Successfully updated Cancel transition to 'All' and cleaned up redundant rules.")
    else:
        print("Workflow is already in the correct state. No updates were necessary.")

