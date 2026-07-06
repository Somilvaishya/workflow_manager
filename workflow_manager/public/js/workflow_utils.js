window.workflow_manager = window.workflow_manager || {};

workflow_manager.prompt_workflow_action_comment = function(frm, action, title, field_label, callback) {
    frappe.dom.unfreeze();

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
