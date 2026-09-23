from odoo import models, fields


class UnicolCrmProductItem(models.Model):
    _name = "unicol.crm.product.item"
    _description = "CRM Product Item (Configuration)"
    _order = "name"

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    _name_uniq = models.Constraint(
        'unique(name)',
        "This product item already exists.",
    )