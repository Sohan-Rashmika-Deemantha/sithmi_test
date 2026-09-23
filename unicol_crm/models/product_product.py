from odoo import models, api
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _search_display_name(self, operator, value):
        """Let users find a product by typing its UC No (e.g. ``UC00056``)
        in addition to its name, from any Many2one field pointing to
        ``product.product`` (sale/purchase lines, GRN lines, quality
        checks, wash records, etc.).

        The base behaviour (search by name/reference/barcode) is kept and
        simply OR-ed with a match on the linked template's ``uc_no``.
        """
        domain = super()._search_display_name(operator, value)
        if value:
            uc_no_domain = [('product_tmpl_id.uc_no', operator, value)]
            domain = expression.OR([domain, uc_no_domain])
        return domain

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Include UC No in the product lookup used by all product selectors.

        This ensures that variant searches also match the linked template's UC No,
        not only the standard name/default_code/barcode fields.
        """
        if not name:
            return super().name_search(name, domain, operator, limit)

        results = super().name_search(name, domain, operator, limit)
        if limit and len(results) >= limit:
            return results

        uc_no_domain = expression.AND([domain or [], [('product_tmpl_id.uc_no', operator, name)]])
        extra_records = self.search_fetch(uc_no_domain, ['display_name'], limit=limit)
        merged = {record_id: display_name for record_id, display_name in results}
        for record in extra_records:
            if record.id not in merged:
                merged[record.id] = record.display_name
        return list(merged.items())[:limit]

    def _compute_display_name(self):
        """Build the product (variant) display name in Unicol's required format:

            [uc_no] name product_item_id (value_ids)

        Example: [UC00056] 276115 ItemXYZ (Blue oxford)

        - ``uc_no`` comes from the linked product template (e.g. UC00056).
        - ``name`` is the product's own name (e.g. 276115).
        - ``product_item_id`` is the Product Item set on the linked
          product template, appended right after the name when set.
        - ``(value_ids)`` is the variant's attribute value combination
          (e.g. Blue oxford), appended last, only added when the product
          actually has variant values.

        This changes what shows up wherever a product is searched/selected
        by ``product_id`` (Many2one dropdowns, list/kanban views, etc.).
        """
        for product in self:
            uc_no = product.product_tmpl_id.uc_no
            display_name = "[%s] %s" % (uc_no, product.name) if uc_no else product.name
            product_item = product.product_tmpl_id.product_item_id
            if product_item:
                display_name = "%s %s" % (display_name, product_item.display_name)
            combination_name = product.product_template_attribute_value_ids._get_combination_name()
            if combination_name:
                display_name = "%s (%s)" % (display_name, combination_name)
            product.display_name = display_name