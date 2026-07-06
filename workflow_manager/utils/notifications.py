import frappe

def send_raven_notification(recipient, message, link_doctype=None, link_document=None):
    """
    Sends a direct message notification to a recipient using an available Raven Bot.
    Ensures that the recipient exists as a Raven User before sending.
    """
    if not recipient:
        return

    # 1. Ensure the recipient is a Raven User
    ensure_raven_user_exists(recipient)

    # 2. Get the bot
    bot_name = None
    if frappe.db.exists("Raven Bot", "Accounts Bot"):
        bot_name = "Accounts Bot"
    else:
        bot_name = frappe.db.get_value("Raven Bot", {}, "name")

    if not bot_name:
        frappe.log_error(f"No Raven Bot found to send notification to {recipient}", "Workflow Manager")
        return

    bot = frappe.get_doc("Raven Bot", bot_name)

    # 3. Send message
    bot.send_direct_message(
        user_id=recipient,
        text=message,
        link_doctype=link_doctype,
        link_document=link_document,
        markdown=True
    )

def ensure_raven_user_exists(user_id):
    """
    Ensures that the given user has a Raven User profile.
    """
    if not user_id:
        return

    from raven.utils import get_raven_user
    if not get_raven_user(user_id):
        if frappe.db.exists("User", user_id):
            user_doc = frappe.get_doc("User", user_id)
            
            # Add Raven User role to User if not present
            if "Raven User" not in [r.role for r in user_doc.roles]:
                user_doc.append("roles", {"role": "Raven User"})
                user_doc.save(ignore_permissions=True)

            # Insert Raven User record if not present
            if not frappe.db.exists("Raven User", {"user": user_id}):
                ru = frappe.new_doc("Raven User")
                ru.user = user_id
                ru.full_name = user_doc.full_name or user_id
                ru.insert(ignore_permissions=True)
