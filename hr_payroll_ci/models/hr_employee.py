# -*- coding:utf-8 -*-
from odoo.addons.base.models.decimal_precision import dp
from odoo import models, api, fields, exceptions, _
from dateutil.relativedelta import relativedelta
from collections import namedtuple
from datetime import datetime


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    cmu_employe = fields.Integer(string='CMU employé', store=True, readonly=True, compute='_compute_cmu_amount',
                                 digits_compute=dp.get_precision('Account'))
    cmu_employe2 = fields.Integer(readonly=True, digits_compute=dp.get_precision('Account'), string='CMU employé')
    cmu_employeur = fields.Integer(store=True, readonly=True, compute='_compute_cmu_amount',
                                   digits_compute=dp.get_precision('Account'), string='CMU employeur')
    cmu_employeur2 = fields.Integer(readonly=True, digits_compute=dp.get_precision('Account'), string='CMU employeur')

    def _compute_cmu_amount(self):
        for rec in self:
            emp_id = rec.ids[0]
            employee = rec.env['hr.employee'].search([('id', '=', emp_id)])
            if employee:
                number_cmu = 1
                enfants_ids = employee.enfants_ids
                if len(enfants_ids) != 0:
                    for enfant in enfants_ids:
                        date_ref = datetime.now().strftime('%Y-%m-%d')
                        date_naiss = enfant.date_naissance
                        temp1 = datetime.strptime(date_ref, '%Y-%m-%d')
                        temp2 = datetime.strptime(str(date_naiss), '%Y-%m-%d')
                        age = abs(relativedelta(temp2, temp1).years)
                        if 0 < age <= 21:
                            number_cmu += 1
                    cmu = 1000 * number_cmu
                    cmu_employe2 = (cmu * 50) / 100
                    cmu_employeur2 = (cmu * 50) / 100
                    rec.cmu_employe = cmu_employe2
                    rec.cmu_employeur = cmu_employeur2
                    employee.write({'cmu_employe2': cmu_employe2})
                    employee.write({'cmu_employeur2': cmu_employeur2})
                else:
                    cmu = 1000 * number_cmu
                    cmu_employe2 = (cmu * 50) / 100
                    cmu_employeur2 = (cmu * 50) / 100
                    rec.cmu_employe = cmu_employe2
                    rec.cmu_employeur = cmu_employeur2
                    employee.write({'cmu_employe2': cmu_employe2})
                    employee.write({'cmu_employeur2': cmu_employeur2})
            else:
                rec.cmu_employe = 0

    def checkOverlappingDate(self, slip_date_start, slip_date_to):
        number_of_days  = 0
        Range = namedtuple('Range', ['start', 'end'])
        r1 = Range(start=slip_date_start, end=slip_date_to)
        self._cr.execute(
            "SELECT id FROM hr_leave WHERE (date_payment"
            " between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd'))"
            " AND state='validate' AND payslip_status = True AND employee_id = %s AND subtract_worked_days = True ",
            (str(slip_date_start), str(slip_date_to), self.id))
        leave_ids = [x[0] for x in self.env.cr.fetchall()]
        leaves = self.env['hr.leave'].browse(leave_ids)
        if leaves:
            for leave in leaves:
                date_from = fields.Date.from_string(leave.date_from)
                date_to = fields.Date.from_string(leave.date_to)
                r2 = Range(start=date_from, end=date_to)
                result = (min(r1.end, r2.end) - max(r1.start, r2.start)).days
                number_of_days += result
        return number_of_days


    def getWorkedDays(self, date_from, date_to, contract):
        att_obj = self.env['hr.attendance']
        res = []
        hours = 0
        if self.type in ('j', 'h'):
            self.env.cr.execute("SELECT id, check_in, check_out FROM hr_attendance WHERE (check_in"
                   " between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd')) AND"
                    "(check_out between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd'))"
                       " AND employee_id=%s",(date_from,date_to,date_from,date_to,self.id))
            for x in self.env.cr.dictfetchall():
                date_start = fields.Datetime.from_string(x['check_in'])
                date_end = fields.Datetime.from_string(x['check_out'])
                tmp = relativedelta(date_end, date_start)
                hours+= tmp.hours
            days = hours/8
            id_work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1).id
            vals = {
                'name': _("Nombre de jours travaillés"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': days,
                'number_of_hours': hours,
                'contract_id': contract.id,
                'work_entry_type_id': id_work_entry_type,
            }
            res.append(vals)
        else:
            id_work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1).id
            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': 30,
                'number_of_hours': 173.33,
                'contract_id': contract.id,
                'work_entry_type_id': id_work_entry_type,
            }

            number = self.checkOverlappingDate(date_from, date_to)
            if number != 0:
                attendances['number_of_days'] = attendances['number_of_days'] - number
                attendances['number_of_hours'] = 173.33 * attendances['number_of_days'] / 30
            res.append(attendances)

            results = self.env['hr.leave'].getHolidays(date_from, date_to, self.id)
            if results:
                for line in results:
                    line['contract_id'] = contract.id
                res += results

            return res

