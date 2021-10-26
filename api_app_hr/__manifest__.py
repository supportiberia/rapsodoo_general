# coding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2020 Todooweb
#    (<http://www.rapsodoo.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'API App HR',
    'version': '14.1.1.0.1',
    'category': 'Extra Tools',
    'summary': """API App HR for Odoo""",
    'description': """API App HR for Odoo.""",
    'license': 'AGPL-3',
    'author': "Rapsodoo Iberia",
    'website': "https://www.rapsodoo.com/es/",
    'depends': ['base', 'mail', 'contacts', 'hr', 'hr_contract', 'hr_attendance', 'hr_skills', 'calendar', 'documents'],
    'data': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}