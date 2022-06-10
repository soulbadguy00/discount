from odoo import models, fields


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    parent_id = fields.Many2one("hr.payroll.structure", "Parent")

    def _get_parent_structure(self):
        parent = self.mapped('parent_id')
        if parent:
            parent = parent._get_parent_structure()
        return parent + self

    def get_all_rules(self):
        """
        @return: returns a list of tuple (id, sequence) of rules that are maybe to apply
        """
        all_rules = []
        for struct in self:
            all_rules += struct.rule_ids._recursive_search_of_rules()
        return all_rules


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure.type"

    parent_id = fields.Many2one("hr.payroll.structure.type", "Parent")

    def _get_parent_structure(self):
        parent = self.mapped('parent_id')
        if parent:
            parent = parent._get_parent_structure()
        return parent + self
