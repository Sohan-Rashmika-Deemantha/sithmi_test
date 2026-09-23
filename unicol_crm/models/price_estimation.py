from odoo import api, fields, models


class PriceEstimation(models.Model):
    _name = "crm.price.estimation"
    _description = "Price Estimation for CRM Opportunities"
    _order = "id DESC"

    name = fields.Char(string='Estimation Reference', required=True)
    crm_lead_id = fields.Many2one('crm.lead', string='Opportunity', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    fallout = fields.Integer(string='Fallout')
    production_capacity = fields.Integer(string='Production Capacity')  
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    total_price = fields.Float(string='Total Price', compute='_compute_total_price', store=True)

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    wet_process_cost = fields.Monetary(
        string='Wet Process Cost',
        currency_field='currency_id',
    )
    wet_process_line_ids = fields.One2many(
        'crm.price.estimation.wet.process',
        'price_estimation_id',
        string='Wet Processes'
    )
    dry_process_line_ids = fields.One2many(
        'crm.price.estimation.dry.process',
        'price_estimation_id',
        string='Dry Processes'
    )

    @api.depends('wet_process_cost', 'dry_process_line_ids.process_cost')
    def _compute_total_price(self):
        for record in self:
            dry_total = sum(record.dry_process_line_ids.mapped('process_cost'))
            record.total_price = record.wet_process_cost + dry_total

    def action_set_approved(self):
        self.write({'state': 'approved'})

    def action_set_cancel(self):
        self.write({'state': 'cancel'})

    def action_set_draft(self):
        self.write({'state': 'draft'})


class PriceEstimationWetProcess(models.Model):
    _name = 'crm.price.estimation.wet.process'
    _description = 'Price Estimation Wet Process'

    price_estimation_id = fields.Many2one(
        'crm.price.estimation',
        string='Price Estimation',
        ondelete='cascade',
        required=True
    )
    process_id = fields.Many2one(
        'wash.process',
        string='Wet Process',
        domain=[('wash_location_type', '=', 'wet')],
        required=True
    )
    process_cost = fields.Float(string='Process Cost')


class PriceEstimationDryProcess(models.Model):
    _name = 'crm.price.estimation.dry.process'
    _description = 'Price Estimation Dry Process'

    price_estimation_id = fields.Many2one(
        'crm.price.estimation',
        string='Price Estimation',
        ondelete='cascade',
        required=True
    )
    process_id = fields.Many2one(
        'wash.process',
        string='Dry Process',
        domain=[('wash_location_type', '=', 'dry')],
        required=True
    )
    process_cost = fields.Float(string='Process Cost')