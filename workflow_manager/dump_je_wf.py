import frappe
import json

def run():
    wfs = frappe.get_all("Workflow", filters={"document_type": "Journal Entry"}, pluck="name")
    result = {}
    for wf in wfs:
        doc = frappe.get_doc("Workflow", wf)
        if doc.is_active:
            result[wf] = {
                "states": [{"state": s.state, "doc_status": s.doc_status} for s in doc.states],
                "transitions": [{"state": t.state, "action": t.action, "next_state": t.next_state, "allowed": t.allowed, "condition": t.condition} for t in doc.transitions]
            }
    print("===START_JSON===")
    print(json.dumps(result, indent=2))
    print("===END_JSON===")
