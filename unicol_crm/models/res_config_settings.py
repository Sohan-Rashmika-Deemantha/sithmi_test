from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_crm_email_templates = fields.Boolean(
        string="CRM Email Templates",
        config_parameter="unicol_crm.enable_crm_email_templates",
        help="Enable CRM email template selection fields for customer breakdown emails.",
    )
    customer_breakdown_email_template_id = fields.Many2one(
        'mail.template',
        string="Customer Breakdown Email Template",
        config_parameter="unicol_crm.customer_breakdown_email_template_id",
        help="Choose the email template used for customer breakdown emails.",
    )
    customer_without_breakdown_email_template_id = fields.Many2one(
        'mail.template',
        string="Customer Without Breakdown Email Template",
        config_parameter="unicol_crm.customer_without_breakdown_email_template_id",
        help="Choose the email template used for customer emails without breakdown.",
    )


