# coding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2020 Todooweb
#    (<http://www.todooweb.com>).
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
    'name': 'Helpdesk Pro',
    'version': '15.1.1.0.11',
    'category': 'Helpdesk',
    'summary': """Support, tickets, issues, bugs.""",
    'description': """Improvement to the Helpdesk Tool: support, tickets, issues, bugs.""",
    'license': 'AGPL-3',
    'author': "Todooweb (www.todooweb.com)",
    'website': "https://todooweb.com/",
    'contributors': [
        "Equipo Dev <devtodoo@gmail.com>",
        "Edgar Naranjo <edgarnaranjof@gmail.com>",
    ],
    'support': 'devtodoo@gmail.com',
    'depends': ['base', 'contacts', 'project', 'website', 'web', 'portal', 'hr_timesheet'],
    'data': [
        'data/website_helpdesk.xml',
        'security/helpdesk_security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/helpdesk_ticket_templates.xml',
        'views/helpdesk_ticket_team_views.xml',
        'views/helpdesk_ticket_stage_views.xml',
        'views/helpdesk_ticket_category_views.xml',
        'views/helpdesk_ticket_channel_views.xml',
        'views/helpdesk_ticket_tag_views.xml',
        'views/helpdesk_views.xml',
        # 'views/helpdesk_dashboard_views.xml',
    ],
    "development_status": "Beta",
    # 'images': ['static/description/translate_screenshot.png'],
    # 'live_test_url': 'https://cutt.ly/GRuk6Qu',
    'installable': True,
    'auto_install': False,
    'application': True,
    # 'price': 12.99,
    # 'currency': 'EUR',
}
