import frappe
import json

def run():
    workflows = frappe.get_all("Workflow", filters={"document_type": "Purchase Invoice"}, pluck="name")
    result = {}
    for wf in workflows:
        doc = frappe.get_doc("Workflow", wf)
        result[wf] = {
            "is_active": doc.is_active,
            "states": [{"state": s.state, "doc_status": s.doc_status} for s in doc.states],
            "transitions": [{"state": t.state, "action": t.action, "next_state": t.next_state, "allowed": t.allowed, "condition": t.condition} for t in doc.transitions]
        }
    print("===START_JSON===")
    print(json.dumps(result, indent=2))
    print("===END_JSON===")
