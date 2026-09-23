from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
import re


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _search_display_name(self, operator, value):
        """Let users find a product by typing its UC No (e.g. ``UC00056``)
        in addition to its name, from any Many2one field pointing to
        ``product.template``.

        The base behaviour (search by name/reference/barcode) is kept and
        simply OR-ed with a match on ``uc_no``.
        """
        domain = super()._search_display_name(operator, value)
        if value:
            uc_no_domain = [('uc_no', operator, value)]
            domain = expression.OR([domain, uc_no_domain])
        return domain

    buyer_id = fields.Many2one('res.partner', string='Buyer')
    product_item_id = fields.Many2one('unicol.crm.product.item', string='Product Item', ondelete='set null')
    type_of_wash_id = fields.Many2one('unicol.crm.type.of.wash', string='Type of Wash', ondelete='set null')
    uc_no = fields.Char(string='UC No', readonly=True, copy=False, index=True)
    originating_lead_id = fields.Many2one(
        'crm.lead',
        string='Lead',
        help='Opportunity this product was created from. Changing this will '
             're-fetch the customer address, company name, buyer, product '
             'item and type of wash from the selected lead. A lead can only '
             'ever be linked to one product.',
    )
    customer_address = fields.Char(string='Customer Address')
    crm_company_name = fields.Char(string='Company Name (from Lead)')
    tentative_price = fields.Monetary(
        string='Tentative Price',
        currency_field='currency_id',
        help='Tentative/estimated sales price for this product, shown before '
             'the final price is confirmed.',
    )
    is_accessory_product = fields.Boolean(string='Is Accessory Product', default=False, copy=False, index=True)

    @api.constrains('purchase_ok', 'originating_lead_id')
    def _check_purchase_ok_not_allowed_for_lead_products(self):
        """A product created from (linked to) a CRM lead can never be
        marked as purchasable. This restriction only applies to products
        that originate from a lead; regular products are unaffected."""
        for product in self:
            if product.originating_lead_id and product.purchase_ok:
                raise ValidationError(_(
                    'The product "%(product)s" was created from the '
                    'opportunity "%(lead)s". Products created from a CRM '
                    'lead cannot be marked as "Can be Purchased".',
                    product=product.display_name,
                    lead=product.originating_lead_id.display_name,
                ))

    def _is_wash_category_product(self, vals=None):
        """Return True when the product category is marked as a wash category."""
        categ_id = vals.get('categ_id') if vals else self.categ_id.id
        if not categ_id:
            return False
        category = self.env['product.category'].browse(categ_id)
        return bool(category and category.is_wash_category)

    def _get_last_price_estimation_total(self, lead_id):
        """Get the total_price from the last (most recent) price estimation for a lead.
        
        Args:
            lead_id: The ID of the crm.lead
            
        Returns the total_price value or 0.0 if no price estimations exist.
        """
        if not lead_id:
            return 0.0
        price_estimation = self.env['crm.price.estimation'].search(
            [('crm_lead_id', '=', lead_id)],
            order='id DESC',
            limit=1
        )
        return price_estimation.total_price if price_estimation else 0.0

    @api.constrains('uc_no', 'is_accessory_product')
    def _check_uc_no_unique(self):
        for product in self:
            if not product.uc_no:
                continue

            # Accessory products are allowed to share the parent's UC No.
            if product.is_accessory_product:
                continue

            duplicate = self.env['product.template'].search([
                ('uc_no', '=', product.uc_no),
                ('id', '!=', product.id),
                ('is_accessory_product', '=', False),
            ], limit=1)

            if duplicate:
                raise ValidationError(_(
                    'UC No "%(uc_no)s" is already used by product '
                    '"%(existing)s". Each normal product must have a '
                    'unique UC No.',
                    uc_no=product.uc_no,
                    existing=duplicate.display_name,
                ))

    @api.onchange('originating_lead_id')
    def _onchange_originating_lead_id(self):
        """When the Lead field is set or changed directly on the product
        form, automatically (re)fetch the related opportunity data including the image."""
        for record in self:
            lead = record.originating_lead_id
            if not lead:
                continue
            if lead.product_template_id and lead.product_template_id.id != record.id:
                raise UserError(_(
                    "The opportunity '%(lead)s' already has a product "
                    "('%(product)s'). A lead can only be linked to one "
                    "product.",
                    lead=lead.name,
                    product=lead.product_template_id.display_name,
                ))
            if 'customer_id' in record._fields:
                record.customer_id = lead.partner_id or False
            if 'customer_address' in record._fields:
                if record._fields['customer_address'].compute:
                    # If the field is computed by another module, keep it driven by customer_id.
                    pass
                else:
                    record.customer_address = lead.customer_address or lead.street or False
            lead.customer_address = lead.customer_address or lead.street or False
            record.crm_company_name = lead.partner_name or False
            record.company_id = lead.company_id or False
            record.buyer_id = lead.buyer_id or lead.partner_id or False
            record.product_item_id = lead.product_item_id or False
            record.type_of_wash_id = lead.type_of_wash_id or False
            # Products created from / linked to a CRM lead can never be
            # purchasable.
            record.purchase_ok = False
            # Products created from / linked to a CRM lead must be storable
            # and tracked by lot
            record.is_storable = True
            record.tracking = 'lot'
            # Set list_price from the last price estimation
            last_price_total = self._get_last_price_estimation_total(lead.id)
            if last_price_total:
                record.list_price = last_price_total
            if 'shipment_type' in record._fields and hasattr(lead, 'shipment_type'):
                record.shipment_type = lead.shipment_type or False
            if 'payment_type' in record._fields and hasattr(lead, 'payment_type'):
                record.payment_type = lead.payment_type or False
            if 'product_tag_ids' in record._fields:
                if hasattr(lead, '_get_or_create_product_tag_ids'):
                    product_tag_ids = lead._get_or_create_product_tag_ids()
                else:
                    product_tag_ids = [tag.id for tag in lead.tag_ids] if hasattr(lead, 'tag_ids') else []
                record.product_tag_ids = [(6, 0, product_tag_ids)] if product_tag_ids else False
            record.name = lead.name or False
            record.image_1920 = (
                lead.image_1920
                if hasattr(lead, 'image_1920') and lead.image_1920
                else lead.image if lead.image else False
            )

    @api.model
    def create(self, vals_list):
        ctx = dict(self._context or {})
        default_originating_lead = ctx.get('default_originating_lead_id')
        default_context_image = ctx.get('default_image_1920') or ctx.get('default_image') or False
        single = isinstance(vals_list, dict)
        vals_iter = [vals_list] if single else vals_list
        lead_ids_to_check = set()
        for v in vals_iter:
            if not isinstance(v, dict):
                continue
            lead_id = v.get('originating_lead_id') or default_originating_lead
            if lead_id:
                lead_ids_to_check.add(int(lead_id))

        if lead_ids_to_check:
            leads = self.env['crm.lead'].browse(lead_ids_to_check)
            for lead in leads:
                if lead.exists() and lead.product_template_id:
                    raise UserError(_(
                        "The opportunity '%(lead)s' already has a product "
                        "('%(product)s'). A lead can only be linked to one "
                        "product - open the existing product instead of "
                        "creating a new one.",
                        lead=lead.name,
                        product=lead.product_template_id.display_name,
                    ))

        for v in vals_iter:
            if isinstance(v, dict):

                # Accessory products receive their parent's UC No.
                # Only wash-category products receive a brand-new UC No.
                if v.get('is_accessory_product'):
                    # The accessory product creation code must provide
                    # the parent's UC No.
                    if not v.get('uc_no'):
                        raise ValidationError(_(
                            'An accessory product must have the UC No of its parent product.'
                        ))

                elif self._is_wash_category_product(v):
                    if not v.get('uc_no'):
                        v['uc_no'] = self.env['ir.sequence'].next_by_code(
                            'product.template.uc_no'
                        )
                elif v.get('uc_no'):
                    raise ValidationError(_(
                        'UC No can only be generated for products in a wash category.'
                    ))

                if default_originating_lead:
                    v.setdefault(
                        'originating_lead_id',
                        default_originating_lead
                    )

                if default_context_image and not v.get('image_1920'):
                    v['image_1920'] = default_context_image

                lead_id = (
                    int(v.get('originating_lead_id'))
                    if v.get('originating_lead_id')
                    else False
                )

                if lead_id:
                    v['purchase_ok'] = False
                    v.setdefault('is_storable', True)
                    v.setdefault('tracking', 'lot')
                    
                    # Set list_price from the last price estimation if not already set
                    if not v.get('list_price'):
                        last_price_total = self._get_last_price_estimation_total(lead_id)
                        if last_price_total:
                            v['list_price'] = last_price_total

                    lead = self.env['crm.lead'].browse(lead_id)

                    if lead.exists():
                        if not v.get('image_1920'):
                            v['image_1920'] = (
                                lead.image_1920
                                if hasattr(lead, 'image_1920')
                                and lead.image_1920
                                else lead.image
                                if lead.image
                                else False
                            )

                        if (
                            'customer_address' in self._fields
                            and not self._fields['customer_address'].compute
                        ):
                            if (
                                not v.get('customer_address')
                                and (lead.customer_address or lead.street)
                            ):
                                v['customer_address'] = (
                                    lead.customer_address or lead.street
                                )

        records = super().create(vals_list)

        if default_originating_lead:
            lead = self.env['crm.lead'].browse(int(default_originating_lead))
            if lead.exists():
                for record in records:
                    lead_vals = {}
                    lead_vals['product_template_id'] = record.id
                    if record.product_item_id:
                        lead_vals['product_item_id'] = record.product_item_id.id
                    if record.type_of_wash_id:
                        lead_vals['type_of_wash_id'] = record.type_of_wash_id.id
                    if record.buyer_id:
                        lead_vals['buyer_id'] = record.buyer_id.id
                    if record.customer_address:
                        lead_vals['street'] = record.customer_address
                        lead_vals['customer_address'] = record.customer_address
                    if record.crm_company_name:
                        lead_vals['partner_name'] = record.crm_company_name
                    lead.write(lead_vals)
        return records

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Include UC No in the product lookup used by all relation fields.

        Some selection widgets use the dedicated ``name_search`` path instead of
        ``_search_display_name``, so we extend that flow with the UC No match and
        merge the extra hits back into the normal result set.
        """
        if not name:
            return super().name_search(name, domain, operator, limit)

        results = super().name_search(name, domain, operator, limit)
        if limit and len(results) >= limit:
            return results

        uc_no_domain = expression.AND([domain or [], [('uc_no', operator, name)]])
        extra_records = self.search_fetch(uc_no_domain, ['display_name'], limit=limit)
        merged = {record_id: display_name for record_id, display_name in results}
        for record in extra_records:
            if record.id not in merged:
                merged[record.id] = record.display_name
        return list(merged.items())[:limit]