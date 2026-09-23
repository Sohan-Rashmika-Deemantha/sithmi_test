from odoo import models, fields

class UnicolCrmTypeOfWash(models.Model):
    _name = "unicol.crm.type.of.wash"
    _description = "CRM Type of Wash (Configuration)"
    _order = "name"

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    _name_uniq = models.Constraint(
        'unique(name)',
        "This type of wash already exists.",
    )