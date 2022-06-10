# -*- encoding: utf-8 -*-

##############################################################################
#
# Copyright (c) 2014 Rodolphe Agnero - support.Rodolphe Agnero.net
# Author: Rodolphe Agnero
#
# Fichier du module hr_payroll_ci
# ##############################################################################  -->


import time
from datetime import date
from datetime import datetime, time
from datetime import timedelta
from dateutil import relativedelta

from odoo import netsvc
from odoo import fields, osv, api, models
from odoo import tools
from odoo.tools.translate import _
from odoo.exceptions import Warning, ValidationError

from odoo.tools.safe_eval import safe_eval as eval
from decimal import Decimal
from collections import namedtuple
from math import fabs, ceil
# from odoo.tools import format_amount

import babel

import odoo.addons.decimal_precision as dp


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def get_days_periode(self, start, end):
        r = (end + timedelta(days=1) - start).days
        return [start + timedelta(days=i) for i in range(r)]

    def write(self, vals):
        emp_obj = self.env['hr.employee']
        trouver = False
        for payslip in self:
            employee = payslip.employee_id
            list_payslips = employee.slip_ids
            date_from = fields.Datetime.from_string(payslip.date_from)
            date_to = fields.Datetime.from_string(payslip.date_to)
            Range = namedtuple('Range', ['start', 'end'])
            r1 = Range(start=date_from, end=date_to)
            new_list = []
            if (len(list_payslips) != 1):
                for slip in list_payslips:
                    if slip.id != payslip.id:
                        new_list.append(slip)
                for slip in new_list:
                    old_date_from = fields.Datetime.from_string(slip.date_from)
                    old_date_to = fields.Datetime.from_string(slip.date_to)
                    r2 = Range(start=old_date_from, end=old_date_to)
                    result = (min(r1.end, r2.end) - max(r1.start, r2.start)).days + 1
            if trouver == True:
                raise ValidationError(_("L'employé possède déjà un bulletin pour cette période"))
            else:
                super(HrPayslip, self).write(vals)
        return True

    # def _get_worked_day_lines(self):
    #     if self.employee_id:
    #     return

    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        super()._onchange_employee()
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            self.input_line_ids = []
            self.worked_days_line_ids = []
            self.contract_id = False
            self.struct_id = False
            self.name = False
            return

        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        contract_ids = []

        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        locale = self.env.context.get('lang') or 'en_US'
        self.name = _('Salary Slip of %s for %s') % (
        employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
        self.company_id = employee.company_id

        if not self.env.context.get('contract') or not self.contract_id:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if not contract_ids:
                return
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])

        if not self.contract_id.struct_id:
            return
        self.struct_id = self.contract_id.struct_id

        # computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
        worked_days_lines = self.worked_days_line_ids.browse([])
        for r in worked_days_line_ids:
            worked_days_lines += worked_days_lines.new(r)
        self.worked_days_line_ids = worked_days_lines
        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        input_lines = self.input_line_ids.browse([])
        for r in input_line_ids:
            input_lines += input_lines.new(r)
        self.input_line_ids = input_lines
        return

    def get_emprunt_montant_monthly(self, employee_id, date_from, date_to):
        ech_obj = self.env['hr.emprunt.loaning.line']
        if employee_id and date_from and date_to:
            lines = ech_obj.search([]).filtered(
                lambda l: l.loaning_id.employee_id == employee_id and l.statut_echeance == 'Take')
            true_line = lines.filtered(lambda t: t.date_prevu >= date_from and t.date_prevu <= date_to)
            return true_line
        return False

    @api.depends('contract_id')
    def _get_anciennete(self):
        anciennete = {}
        for slip in self:
            end_date = fields.Datetime.from_string(slip.date_to)
            start_date = fields.Datetime.from_string(slip.employee_id.first_contract_date)
            tmp = relativedelta.relativedelta(end_date, start_date)

            slip.update({
                'payslip_an_anciennete': tmp.years,
                'payslip_mois_anciennete': tmp.months,
            })

    def _get_last_payslip(self):
        dic = {}
        res = []
        for rec in self:
            slips = rec.employee_id.slip_ids
            if (len(slips) == 1):
                rec.last_payslip = False
            else:
                for slip in slips:
                    if (slip.id < rec.id):
                        res.append(slip)
                        if len(res) >= 1:
                            dernier = res[len(res) - 1]
                            payslip = rec.self.env['hr.payslip'].search([('id', '=', dernier.id)])
                            rec.last_payslip = payslip.id

    def _get_total_gain(self):
        res = {}
        # line_obj=self.pool.get("hr.payslip.line")
        for rec in self:
            for line in rec.line_ids:
                if line.code == 'BRUT':
                    self.total_gain = line.total
            return res

    def _get_retenues(self):
        for rec in self:
            for line in rec.line_ids:
                if line.code == 'RET':
                    rec.total_retenues = line.total

    @api.depends('line_ids.total')
    def _get_net_paye(self):
        for slip in self:
            for line in slip.line_ids:
                if line.code == "NET":
                    slip.update({
                        'net_paie': line.total,
                    })

    def get_amountbycode(self, code, line_ids):
        # line_obj = self.env['hr.payslip.line']
        amount = 0
        if line_ids:
            for line in line_ids:
                if line.code == code:
                    return line.amount
        return 0

    def cumulBYCode(self, employee_id, code, date_from, date_to):
        slip_obj = self.env['hr.payslip']
        payslips = slip_obj.search([('date_from', '>=', date_from), ('date_to', '<=', date_to),
                                    ('employee_id', '=', employee_id)])
        total_amount = 0
        for slip in payslips:
            result = slip.get_amountbycode(code, slip.line_ids)
            total_amount += result
        return total_amount

    def get_cumul_base_impot(self):

        for payslip in self:
            year = datetime.now().year
            date_temp = fields.Datetime.from_string(payslip.date_from)
            first_day = str(date_temp + relativedelta.relativedelta(month=1, day=1))[:10]
            total = payslip.cumulBYCode(payslip.employee_id.id, 'SNI', first_day, payslip.date_from)
            worked_days = payslip.cumulBYCode(payslip.employee_id.id, 'TJRPAY', first_day, payslip.date_from)
            date_to = fields.Datetime.from_string(payslip.date_to)
            payslip.update({
                'cumul_base_impot': payslip.cumulBYCode(payslip.employee_id.id, 'SNI', first_day, payslip.date_from),
                'cumul_cn': payslip.cumulBYCode(payslip.employee_id.id, 'CN', first_day, payslip.date_from),
                'cumul_worked_days': payslip.cumulBYCode(payslip.employee_id.id, 'TJRPAY', first_day,
                                                         payslip.date_from),
                'cumul_igr': payslip.cumulBYCode(payslip.employee_id.id, 'IGR', first_day, payslip.date_from),
                'number_of_month': date_to.month
            })

    def get_somme_rubrique(self, code):
        annee = self.date_to.year
        for payslip in self:
            cpt = 0
            for line in self.line_ids:
                if line.salary_rule_id.code == code and self.date_to >= self.date_to and payslip.date_to.year == annee:
                    cpt += line.total
            result = cpt
            return result

    def get_amount_rubrique(self, rubrique):
        # for id in range(len(obj)):
        line_ids = self.line_ids
        total = 0
        for line in line_ids:
            if line.code == rubrique:
                total = line.total
        # result = format_amount.manageSeparator(total)
        result = total
        return result

    def getTauxByCode(self, rubrique):
        # for id in range(len(obj)):
        taux = 0.0
        lines = self.line_ids
        for line in lines:
            if line.code == rubrique:
                taux = line.rate
        return taux

    def getLineByCode(self, code):
        # for id in range(len(obj)):
        lines = self.line_ids
        for line in lines:
            if line.code == code:
                return line

    def _get_total(self):
        self.worked_days = 0.0

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        res = []
        # res = self.get_inputs(contracts, date_from, date_to)
        for contract in contracts:
            inputs = contract.employee_id.getInputsPayroll(contract, date_from, date_to)
            res += inputs
        return res

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        res = []

        for contract in contracts:
            employee = contract.employee_id
            if employee:
                worked_days = employee.getWorkedDays(date_from, date_to, contract)
                res += worked_days
                overtimes_days = employee.getWorkInput(contract, date_from, date_to)
                res += overtimes_days
        return res

    @api.depends("line_ids")
    def _get_basic_element(self):
        for slip in self:
            base_daily = slip.line_ids.filtered(lambda l: l.code == 'BASE_J')
            brut_imposable = slip.line_ids.filtered(lambda l: l.code == 'BRUT')
            brut_total = slip.line_ids.filtered(lambda l: l.code == 'BRUT_TOTAL')
            if base_daily:
                slip.base_daily = base_daily.total
            if brut_imposable:
                slip.brut_imposable = brut_imposable.total
            if brut_total:
                slip.brut_total = brut_total.total

    option_salaire = fields.Selection([('mois', 'Mensuel'), ('jour', 'Journalier'), ('heure', 'horaire')],
                                      'Option salaire', index=True, readonly=False)
    reference_reglement = fields.Char('Reférence', size=60, required=False)
    payslip_an_anciennete = fields.Integer("Nombre d'année", compute=_get_anciennete)
    payslip_mois_anciennete = fields.Integer("Nombre de mois(Ancienneté)", compute=_get_anciennete)
    payment_method = fields.Selection([('espece', 'Espèces'), ('virement', 'Virement bancaire'), ('cheque', 'Chèques')],
                                      string='Moyens de paiement', required=False, default='espece')
    last_payslip = fields.Many2one("hr.payslip", compute=_get_last_payslip, store=True, string="Dernier bulletin")
    total_gain = fields.Integer(compute=_get_total_gain, store=True)
    total_retenues = fields.Integer(compute=_get_retenues, store=True)
    net_paie = fields.Integer(compute=_get_net_paye, store=True)
    cumul_base_impot = fields.Float('Cumul base impôt', compute=get_cumul_base_impot)
    cumul_cn = fields.Float('Cumul CN payé', compute=get_cumul_base_impot)
    cumul_igr = fields.Float('Cumul IGR payé', compute=get_cumul_base_impot)
    cumul_worked_days = fields.Float('Cumul jours travaillés', compute=get_cumul_base_impot)
    worked_days = fields.Float('Total jours travaillés', compute=_get_total)
    number_of_month = fields.Integer('Nombre de mois', compute='get_cumul_base_impot',store=True)
    type = fields.Selection(selection=[('h', 'Horaire'), ('j', 'Journalier'), ('m', 'Mensuel')],
                            related="employee_id.type", string='Type (Rémunération)', store=True)
    department_id = fields.Many2one('hr.department', 'Departement', related="employee_id.department_id")
    nature_employe = fields.Selection(selection=[('local', 'Local'), ('expat', 'Expatrié')],
                                      related='employee_id.nature_employe', string="Nature de l'employé", store=True)
    base_daily = fields.Float("Base journalière", compute="_get_basic_element", store=True)
    brut_imposable = fields.Float("Brut imposable", compute="_get_basic_element", store=True)
    brut_total = fields.Float("Brut Total", compute="_get_basic_element", store=True)

    def get_list_employee(self):
        list_employees = []
        hcontract_ids = self.env('hr.contract').search([('state', '=', 'in_progress')])
        self.env.cr.execute("SELECT employee_id FROM hr_contract WHERE id=ANY(%s)", (hcontract_ids,))
        results = self.env.cr.fetchall()
        if results:
            list_employees = [res[0] for res in results]
            return {'domain': {'employee_id': [('id', 'in', list_employees)]}}

    def get_net_paye(self):
        montant = 0
        # line_obj=self.pool.get("hr.payslip.line")
        for line in self.line_ids:
            if line.code == "NET":
                montant = line.total
        return montant

    def get_brut_amount(self):
        brut_amount = 0
        for line in self.line_ids:
            if line.code == 'BRUT':
                brut_amount = line.total
        return brut_amount

    @api.model
    def get_contract(self, employee, date_from, date_to):
        """
        @param employee: recordset of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        # a contract is valid if it ends between the given dates
        clause_1 = ['&', ('date_end', '<=', date_to), ('date_end', '>=', date_from)]
        # OR if it starts between the given dates
        clause_2 = ['&', ('date_start', '<=', date_to), ('date_start', '>=', date_from)]
        # OR if it starts before the date_from and finish after the date_end (or never finish)
        clause_3 = ['&', ('date_start', '<=', date_from), '|', ('date_end', '=', False), ('date_end', '>=', date_to)]
        clause_final = [('employee_id', '=', employee.id), ('state', '=', 'open'), '|',
                        '|'] + clause_1 + clause_2 + clause_3
        return self.env['hr.contract'].search(clause_final).ids

    # @api.model
    # def get_inputs(self, contracts, date_from, date_to):
    #     res = []
    #
    #     structure_ids = contracts.get_all_structures()
    #     rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
    #     sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]
    #     inputs = self.env['hr.salary.rule'].browse(sorted_rule_ids).mapped('input_ids')
    #
    #     for contract in contracts:
    #         for input in inputs:
    #             input_data = {
    #                 'name': input.name,
    #                 'code': input.code,
    #                 'contract_id': contract.id,
    #             }
    #             res += [input_data]
    #     return res


class hr_payslip_line(models.Model):
    '''
    Payslip Line
    '''

    _name = 'hr.payslip.line'
    _inherit = 'hr.payslip.line'
    _description = "hr payslip line"

    def _calculate_total(self):
        if not self: return {}
        res = {}
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    def _get_element(self):
        for line in self:
            line.date_from = line.slip_id.date_from
            line.date_to = line.slip_id.date_to

    amount = fields.Float('Amount', digits=(16, 0))
    quantity = fields.Float('Quantity', digits=(16, 4))
    rate = fields.Float(string='Rate (%)', digits=(16, 2), default=100)
    total = fields.Float(compute='_compute_total', string='Total', digits=(16, 0), store=True)
    date_from = fields.Date(string='Date From', compute='_get_element', store=True)
    date_to = fields.Date(string='Date To', compute='_get_element', store=True)


class hr_salary_rule(models.Model):
    _inherit = 'hr.salary.rule'
    _order = 'sequence'

    parent_rule_id = fields.Many2one('hr.salary.rule', string='Parent Salary Rule', index=True)
    child_ids = fields.One2many('hr.salary.rule', 'parent_rule_id', string='Child Salary Rule', copy=True)
    input_ids = fields.One2many('hr.rule.input', 'input_id', string='Inputs', copy=True)

    def _recursive_search_of_rules(self):
        """
        @return: returns a list of tuple (id, sequence) which are all the children of the passed rule_ids
        """
        children_rules = []
        for rule in self.filtered(lambda rule: rule.child_ids):
            children_rules += rule.child_ids._recursive_search_of_rules()
        return [(rule.id, rule.sequence) for rule in self] + children_rules


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.onchange('number_of_days', 'number_of_hours')
    def onChangeElementWD(self):
        if self.code == 'WORK100':
            self.rate = (self.number_of_days / 30)
            self.number_of_hours = (self.number_of_days * 173.33) / 30

    rate = fields.Float('Taux')


class HrRuleInput(models.Model):
    _name = 'hr.rule.input'
    _description = 'Salary Rule Input'

    name = fields.Char(string='Description', required=True)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    input_id = fields.Many2one('hr.salary.rule', string='Salary Rule Input', required=True)
