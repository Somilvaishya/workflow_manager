import frappe

def run():
    wf_name = "Journal Entry Approval Workflow"
    if not frappe.db.exists("Workflow", wf_name):
        print("Workflow not found!")
        return
        
    wf = frappe.get_doc("Workflow", wf_name)
    
    updated = False
    
    # 1. Update Cancel transition to All
    for t in wf.transitions:
        if t.state == "Submitted" and t.action == "Cancel" and t.next_state == "Cancelled":
            if t.allowed != "All":
                t.allowed = "All"
                updated = True
                
    # 2. Cleanup redundant Submit transitions (where All already exists)
    # We have duplicates for Draft -> Submitted, Pending Fix -> Submitted, Rejected -> Submitted
    # Let's remove the "Accounts Approver" ones if "All" is present.
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
                        to_remove.append(x)
                        
    for r in to_remove:
        wf.transitions.remove(r)
        updated = True
        
    if updated:
        wf.save()
        frappe.db.commit()
        print("Successfully updated Cancel transition to 'All' and cleaned up redundant rules.")
    else:
        print("No updates were necessary.")
