# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class ReportTicketClient(models.Model):
    _name = 'report.ticket.client'
    _auto = False
    _description = 'Report Ticket Client'

    name = fields.Char(string='Name', readonly=True)
    client_name = fields.Char('Client name', readonly=True)
    project_name = fields.Char('Project name', readonly=True)
    project_id = fields.Many2one('project.project', 'Project', readonly=True)
    contracted_hours = fields.Float('Contracted hours', readonly=True)
    consumed_hours = fields.Float('Consumed hours')
    remaining_hours = fields.Float('Remaining hours')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER() as id,
                    CONCAT(pp.name,'-', rp.name) as name, 
                    pp.name as project_name,
                    pp.id as project_id,
                    rp.name as client_name,
                    pp.count_hours as contracted_hours,
                    (select sum(aal.unit_amount) as consumed_hours from account_analytic_line aal where aal.project_id=pp.id),
                    pp.count_hours - (select sum(aal.unit_amount) as consumed_hours from account_analytic_line aal where aal.project_id=pp.id) as remaining_hours
                FROM project_project pp
                INNER JOIN res_partner rp
                ON pp.partner_id = rp.id
                WHERE pp.active_plan
                GROUP BY pp.id, pp.name, rp.name, pp.count_hours
            )
            """ % self._table)
