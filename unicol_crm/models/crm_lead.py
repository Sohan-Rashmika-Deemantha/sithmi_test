from odoo import models, fields


class CRMLead(models.Model):
    _inherit = "crm.lead"

    partner_id = fields.Many2one('res.partner', string='Customer')
    customer_address = fields.Char(string='Customer Address')
    buyer_id = fields.Many2one('res.partner', string='Buyer', domain="[('buyer','=','buyer')]")
    crm_email_template_type = fields.Selection(
        [
            ('customer_breakdown_email', 'With Breakdown'),
            ('customer_without_breakdown_email', 'Without Breakdown'),
        ],
        string='CRM Email Template',
        help='Choose which CRM email template type to use when sending email from this opportunity.',
    )
    product_item_id = fields.Many2one(
        'unicol.crm.product.item', string='Product Item', ondelete='set null'
    )
    type_of_wash_id = fields.Many2one(
        'unicol.crm.type.of.wash', string='Type of Wash', ondelete='set null'
    )
    product_template_id = fields.Many2one('product.template', string='Created Product')
    image = fields.Image(string='Image')
    price_estimation_count = fields.Integer(
        string='Price Estimations',
        compute='_compute_price_estimation_count',
        help='Number of price estimations for this opportunity'
    )

    def _compute_price_estimation_count(self):
        """Compute the count of price estimations related to this opportunity."""
        for record in self:
            record.price_estimation_count = self.env['crm.price.estimation'].search_count(
                [('crm_lead_id', '=', record.id)]
            )

    def action_create_product_template(self):
        """Smart-button action behind 'Create Product'.

        - If this opportunity already has a linked product
          (product_template_id is set), open THAT existing product
          instead of a blank create form. A lead may only ever be
          linked to a single product.
        - Otherwise, open a blank Product Template creation form,
          pre-filled from this opportunity's data.
        """
        self.ensure_one()

        if self.product_template_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Product',
                'res_model': 'product.template',
                'res_id': self.product_template_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        product_tag_ids = []
        if hasattr(self, 'tag_ids') and self.tag_ids:
            for lead_tag in self.tag_ids:
                pt = self.env['product.tag'].search([('name', '=', lead_tag.name)], limit=1)
                if not pt:
                    pt = self.env['product.tag'].create({'name': lead_tag.name})
                product_tag_ids.append(pt.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Product',
            'res_model': 'product.template',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': self.name,
                'default_buyer_id': (
                    self.buyer_id.id
                    if self.buyer_id
                    else (self.partner_id.id if self.partner_id else False)
                ),
                'default_customer_id': self.partner_id.id if self.partner_id else False,
                'default_product_item_id': self.product_item_id.id if self.product_item_id else False,
                'default_type_of_wash_id': self.type_of_wash_id.id if self.type_of_wash_id else False,
                'default_originating_lead_id': self.id,
                'default_product_tag_ids': [(6, 0, product_tag_ids)] if product_tag_ids else False,
                'default_customer_address': self.customer_address or False,
                'default_crm_company_name': self.partner_name or False,
                'default_company_id': self.company_id.id if self.company_id else False,
                'default_image_1920': self.image_1920 if hasattr(self, 'image_1920') and self.image_1920 else self.image if self.image else False,
                'default_image': self.image_1920 if hasattr(self, 'image_1920') and self.image_1920 else self.image if self.image else False,
                'default_is_storable': True,
                'default_tracking': 'lot',
                'default_list_price': self._get_last_price_estimation_total(),

            },
        }

    def action_send_email(self):
        """Open the email composition wizard for this lead.

        Always loads the Price Estimation email template (when CRM email
        templates are enabled in Settings). That template itself adapts
        its "Process" section based on crm_email_template_type:
        - 'customer_breakdown_email' (With Breakdown): shows an itemised
          breakdown (wet process cost + each dry process with its cost).
        - 'customer_without_breakdown_email' (Without Breakdown): shows
          just the process names, with no cost breakdown.
        """
        self.ensure_one()

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', raise_if_not_found=False)
        params = self.env['ir.config_parameter'].sudo()

        def _is_enabled(param_name):
            return params.get_param(param_name) in ('True', '1', True, 1)

        template = False
        if _is_enabled('unicol_crm.enable_crm_email_templates'):
            template = self.env.ref('unicol_crm.email_template_price_estimation', raise_if_not_found=False)

        ctx = {
            'default_model': 'crm.lead',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_subject': self.name or False,
            'default_partner_ids': self.partner_id.ids if self.partner_id else [],
            'force_email': True,
        }
        if template and template.exists():
            ctx['default_template_id'] = template.id
            ctx['default_use_template'] = True

        return {
            'name': 'Compose Email',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(compose_form.id if compose_form else False, 'form')],
            'view_id': compose_form.id if compose_form else False,
            'target': 'new',
            'context': ctx,
        }

    def action_view_price_estimation(self):
        """
        Smart button action to view/create price estimations for this opportunity.
        - If price estimations exist, show them in a list view
        - If no price estimations exist, open a create form
        """
        self.ensure_one()

        # Search for existing price estimations for this lead/opportunity
        price_estimations = self.env['crm.price.estimation'].search(
            [('crm_lead_id', '=', self.id)]
        )

        if price_estimations:
            # If price estimations exist, show them in a list view
            price_estimation_view = self.env.ref(
                'unicol_crm.view_price_estimation_list', raise_if_not_found=False
            )
            return {
                'name': 'Price Estimations',
                'type': 'ir.actions.act_window',
                'res_model': 'crm.price.estimation',
                'view_mode': 'list,form',
                'views': [
                    (price_estimation_view.id if price_estimation_view else False, 'list'),
                    (False, 'form'),
                ],
                'domain': [('crm_lead_id', '=', self.id)],
                'context': {
                    'default_crm_lead_id': self.id,
                    'default_name': f'Price Estimation - {self.name}',
                    'default_partner_id': self.partner_id.id if self.partner_id else False,
                },
            }
        else:
            # If no price estimations exist, open a create form
            return {
                'name': 'Create Price Estimation',
                'type': 'ir.actions.act_window',
                'res_model': 'crm.price.estimation',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {
                    'default_crm_lead_id': self.id,
                    'default_name': f'Price Estimation - {self.name}',
                    'default_partner_id': self.partner_id.id if self.partner_id else False,
                },
            }

    def _prepare_opportunity_quotation_context(self):
        """Override parent method to include buyer_id, wash_type_id, product line, 
        wet_process_cost, and dry processes when creating quotations.
        
        Pre-fills:
        - buyer_id and wash_type_id from the opportunity
        - Order line with the product created from this opportunity (if any)
        - Wet process cost from the last price estimation
        - Dry process lines from the last price estimation
        """
        self.ensure_one()
        quotation_context = super()._prepare_opportunity_quotation_context()
        
        if self.buyer_id:
            quotation_context['default_buyer_id'] = self.buyer_id.id
        
        if self.type_of_wash_id:
            quotation_context['default_wash_type_id'] = self.type_of_wash_id.id
        
        # Add product line if a product was created from this lead
        order_line_data = []
        if self.product_template_id:
            # Create order line with the product template
            order_line_data.append((0, 0, {
                'product_id': self.product_template_id.product_variant_ids[0].id if self.product_template_id.product_variant_ids else False,
                'product_uom_qty': 1.0,
            }))
            quotation_context['default_order_line'] = order_line_data if order_line_data else False
        
        # Add wet process cost and dry processes from the last price estimation
        last_price_estimation = self._get_last_price_estimation()
        if last_price_estimation:
            # Set wet process cost
            if last_price_estimation.wet_process_cost:
                quotation_context['default_wet_process_cost'] = last_price_estimation.wet_process_cost
            
            # Add dry process lines from price estimation
            dry_process_line_data = []
            for dry_process in last_price_estimation.dry_process_line_ids:
                dry_process_line_data.append((0, 0, {
                    'process_id': dry_process.process_id.id,
                    'price': dry_process.process_cost,
                }))
            if dry_process_line_data:
                quotation_context['default_dry_process_line_ids'] = dry_process_line_data
        
        return quotation_context

    def _get_or_create_product_tag_ids(self):
        """Return product.tag ids matching this lead's CRM tags (tag_ids),
        creating any product.tag that doesn't exist yet with a matching name.

        Shared by the 'Create Product' smart button context and the
        product.template onchange so both stay in sync.
        """
        self.ensure_one()
        product_tag_ids = []
        if hasattr(self, 'tag_ids') and self.tag_ids:
            for lead_tag in self.tag_ids:
                pt = self.env['product.tag'].search([('name', '=', lead_tag.name)], limit=1)
                if not pt:
                    pt = self.env['product.tag'].create({'name': lead_tag.name})
                product_tag_ids.append(pt.id)
        return product_tag_ids

    def _get_last_price_estimation_total(self):
        """Get the total_price from the last (most recent) price estimation for this lead.
        
        Returns the total_price value or 0.0 if no price estimations exist.
        """
        self.ensure_one()
        price_estimation = self.env['crm.price.estimation'].search(
            [('crm_lead_id', '=', self.id)],
            order='id DESC',
            limit=1
        )
        return price_estimation.total_price if price_estimation else 0.0

    def _get_last_price_estimation(self):
        """Get the last (most recent) price estimation for this lead.
        
        Returns the price_estimation record or False if none exist.
        """
        self.ensure_one()
        price_estimation = self.env['crm.price.estimation'].search(
            [('crm_lead_id', '=', self.id)],
            order='id DESC',
            limit=1
        )
        return price_estimation if price_estimation else False

    def _get_ready_qty(self):
        """Get the ready (on-hand, finished-location) quantity for the
        product created from/linked to this opportunity.

        Kept as a utility method even though the Price Estimation email
        template no longer displays it (the "Estimated Qty" row was
        removed on request).

        Returns 0.0 if there is no linked product.
        """
        self.ensure_one()
        if not self.product_template_id:
            return 0.0
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', self.product_template_id.product_variant_ids.ids),
            ('location_id.is_finished_location', '=', True),
        ])
        return sum(quants.mapped('quantity'))