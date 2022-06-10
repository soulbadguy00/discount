# -*- coding:utf-8 -*-


from odoo import api, fields, models, exceptions


class HrPayrollInverse(models.TransientModel):
    _name = 'hr.payroll.inverse'
    _description = "hr payroll inverse"

    def _get_lines(self):
        active_id = self._context.get('active_id')
        if active_id:
            slip = self.env['hr.payslip'].browse(active_id)
            if slip:
                return [
                    (0, 0, {'rule_id': input.id})
                    for input in slip.input_line_ids
                ]

        return []

    @api.constrains('montant')
    def computeSlip(self):
        for rec in self:
            payslip = rec.env['hr.payslip'].browse(rec._context.get('active_id'))
            contract = payslip.contract_id
            total_intrant = contract.wage
            if rec.line_ids:
                input = contract.sursalaire
                amount_add = 0
                for prime in contract.hr_payroll_prime_ids:
                    total_intrant += prime.montant_prime

                if total_intrant > rec.montant:
                    raise exceptions.ValidationError('Le montant est inféreur aux intrants')

                else:
                    structure_salariale = payslip.struct_id
                    use_anc = False
                    for rule in structure_salariale.rule_ids:
                        if rule.code == 'PANC':
                            use_anc = True
                    if rec.type_calcul == 'brut':
                        if use_anc:
                            prime_anciennete = 0.0
                            if 1 < contract.an_anciennete < 26:
                                prime_anciennete = 0.01 * contract.wage * contract.an_anciennete
                                total_intrant += prime_anciennete
                            brut_add = rec.montant - total_intrant
                            brut_amount = payslip.get_brut_amount()
                            while brut_amount != rec.montant:
                                if brut_amount < rec.montant:
                                    brut_add += rec.montant - brut_amount
                                elif brut_amount > rec.montant:
                                    brut_add -= (brut_amount - rec.montant)
                                contract.sursalaire = brut_add
                                payslip.compute_sheet_by_inverse_calculation()
                                brut_amount = payslip.get_brut_amount()
                        else:
                            brut_add = rec.montant - total_intrant
                            while brut_amount != rec.montant:
                                if brut_amount < rec.montant:
                                    brut_add += rec.montant - brut_amount
                                elif brut_amount > rec.montant:
                                    brut_add -= (brut_amount - rec.montant)
                                contract.sursalaire = brut_add
                                payslip.compute_sheet_by_inverse_calculation()
                                brut_amount = payslip.get_brut_amount()
                    elif rec.type_calcul == 'net':
                        amount_add = input
                        net_amount = payslip.get_net_paye()
                        while net_amount != rec.montant:
                            net_amount = payslip.get_net_paye()
                            if net_amount < rec.montant:
                                amount_add += rec.montant - net_amount
                            elif net_amount > rec.montant:
                                amount_add -= (net_amount - rec.montant)
                            contract.sursalaire = amount_add
                            payslip.compute_sheet_by_inverse_calculation()

    line_ids = fields.One2many('hr.payroll.inverse.line', 'inverse_id', 'Lignes', required=False, default=_get_lines)
    type_calcul = fields.Selection([('brut', 'Par le brut'), ('net', 'Par le net')], 'Méthode de calcul', required=True)
    montant = fields.Integer("Montant ")


class HrPayrollInverseLine(models.TransientModel):
    _name = 'hr.payroll.inverse.line'
    _description = "hr payroll inverse line"

    rule_id = fields.Many2one('hr.payslip.input', 'Règle salariale', required=False)
    inverse_id = fields.Many2one('hr.payroll.inverse', 'Calcul inverse', required=False)
