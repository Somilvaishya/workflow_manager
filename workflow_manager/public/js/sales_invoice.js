frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        frm.trigger('check_b2b_customer');
    },
    customer: function(frm) {
        frm.trigger('check_b2b_customer');
    },
    is_return: function(frm) {
        frm.trigger('check_b2b_customer');
    },
    check_b2b_customer: function(frm) {
        if (frm.doc.customer && frm.doc.is_return === 1) {
            frappe.db.get_value('Customer', frm.doc.customer, 'gstin', (r) => {
                if (r && r.gstin) {
                    frm.set_value('custom_is_b2b_customer', 1);
                } else {
                    frm.set_value('custom_is_b2b_customer', 0);
                }
            });
        } else {
            frm.set_value('custom_is_b2b_customer', 0);
        }
    }
});
