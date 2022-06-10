##############################################################################
#
# Copyright (c) 2012 Rodolphe Agnero - jonathan.arra@gmail.com
# Author: Jean Jonathan ARRA
#
# Fichier du module hr_synthese
# ##############################################################################
{
    "name" : "Payroll Côte d'Ivoire",
    "version" : "1.0",
    "author" : "Rodolphe Agnero",
    'category': 'Localization',
    "website" : "http://www.rodolpheagnero.com",
    "depends" : ["hr_payroll", "hr_contract_extension", 'web','hr_holidays'],
    "description": """ Synthèse de la paie
    - livre de paie mensuelle et périodique
    - Synthèse de paie des employés
    - interfaçage avec la gestion des contrats des employés
    """,
    "init_xml" : [],
    "demo_xml" : [],
    "data":[
        'data/hr_salary_rule_category.xml',
        #'data/hr_salary_rule.xml',
        #"views/hr_payroll_report.xml",
        #"security/hr_security.xml",
        "security/ir.model.access.csv",
        'report/templates/layout_view.xml',
        "wizards/hr_payroll_inverse_view.xml",
        "views/res_company_view.xml",
        "views/report_payslip.xml",
        "views/hr_payroll_ci.xml",
        "views/hr_employee.xml",
    ],
    "installable": True
}
