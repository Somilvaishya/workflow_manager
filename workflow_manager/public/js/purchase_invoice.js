frappe.ui.form.on('Purchase Invoice', {
    before_workflow_action: function(frm) {
        if (frm.selected_workflow_action === 'Pending Recorrection') {
            frappe.dom.unfreeze();

            return new Promise((resolve, reject) => {
                // Reusable fallback helper in case global workflow_utils.js is not loaded yet
                let prompt_comment = (window.workflow_manager && window.workflow_manager.prompt_workflow_action_comment)
                    ? window.workflow_manager.prompt_workflow_action_comment
                    : function(frm, action, title, field_label, callback) {
                        let d = new frappe.ui.Dialog({
                            title: title || __('Remarks Required'),
                            fields: [
                                {
                                    label: field_label || __('Message'),
                                    fieldname: 'comment',
                                    fieldtype: 'Small Text',
                                    reqd: 1
                                }
                            ],
                            primary_action_label: __('Send'),
                            primary_action(values) {
                                if (!values.comment) {
                                    frappe.msgprint(__('This field is required'));
                                    return;
                                }
                                d.hide();
                                if (callback) {
                                    callback(values.comment);
                                }
                            }
                        });
                        d.show();
                    };

                prompt_comment(
                    frm,
                    frm.selected_workflow_action,
                    __('Correction Required'),
                    __('Correction Message'),
                    function(comment) {
                        frappe.call({
                            method: 'workflow_manager.handlers.purchase_invoice.handle_recorrection',
                            args: {
                                docname: frm.doc.name,
                                correction_message: comment
                            },
                            callback: function(r) {
                                if (r.message && r.message.status === 'success') {
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
                // Reject the promise immediately so standard transition does not execute.
                reject();
            });
        }
    }
});
