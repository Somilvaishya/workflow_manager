import frappe

def map_receipt_fields_to_invoice(doc):
    """
    Maps supplier invoice fields from linked Purchase Receipts to the Purchase Invoice.
    Only maps if:
      1. The document is new (doc.is_new()) or target fields are empty.
      2. There is at least one linked Purchase Receipt.
      3. If there are multiple linked Purchase Receipts, their fields must be identical.
         Otherwise, a warning is shown and fields are left empty.
    """
    if not (doc.is_new() or not doc.bill_no):
        return

    # 1. Collect all unique linked Purchase Receipts from items
    pr_names = list(set(
        item.purchase_receipt 
        for item in (doc.get("items") or []) 
        if item.purchase_receipt
    ))

    if not pr_names:
        return

    # 2. Fetch mapping fields for all unique Purchase Receipts
    pr_data_list = frappe.get_all(
        "Purchase Receipt",
        filters={"name": ["in", pr_names]},
        fields=["name", "bill_no", "bill_date", "bns_ewaybill_date", "bns_ewaybill_attachment"]
    )

    if not pr_data_list:
        return

    # 3. Check for consistency across all receipts
    bill_nos = set(d.bill_no for d in pr_data_list if d.bill_no)
    bill_dates = set(d.bill_date for d in pr_data_list if d.bill_date)
    ewaybill_dates = set(d.bns_ewaybill_date for d in pr_data_list if d.bns_ewaybill_date)
    ewaybill_attachments = set(d.bns_ewaybill_attachment for d in pr_data_list if d.bns_ewaybill_attachment)

    # If conflicting values exist, show warning and do not map
    conflicts = []
    if len(bill_nos) > 1:
        conflicts.append("Supplier Invoice No")
    if len(bill_dates) > 1:
        conflicts.append("Supplier Invoice Date")
    if len(ewaybill_dates) > 1:
        conflicts.append("e-Waybill Date")
    if len(ewaybill_attachments) > 1:
        conflicts.append("e-Waybill Attachment")

    if conflicts:
        frappe.msgprint(
            msg=(
                f"Warning: Multiple Purchase Receipts with conflicting details ({', '.join(conflicts)}) "
                "were detected. Supplier Invoice details could not be auto-populated."
            ),
            title="Mapping Warning",
            indicator="orange"
        )
        return

    # If no conflicts, map the unique values (if any)
    unique_bill_no = list(bill_nos)[0] if bill_nos else None
    unique_bill_date = list(bill_dates)[0] if bill_dates else None
    unique_ewaybill_date = list(ewaybill_dates)[0] if ewaybill_dates else None
    unique_ewaybill_attachment = list(ewaybill_attachments)[0] if ewaybill_attachments else None


    if unique_bill_no and not doc.bill_no:
        doc.bill_no = unique_bill_no
    if unique_bill_date and not doc.bill_date:
        doc.bill_date = unique_bill_date
    if unique_ewaybill_date and not doc.bns_ewaybill_date:
        doc.bns_ewaybill_date = unique_ewaybill_date
    if unique_ewaybill_attachment and not doc.bns_ewaybill_attachment:
        doc.bns_ewaybill_attachment = unique_ewaybill_attachment
