from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    buyer = fields.Selection(
        [
            ('buyer', 'Buyer'),
        ],
        string="Buyer",
    )
