from odoo import models, fields, api, tools, _


class Partner(models.Model):
    _inherit = "res.partner"

    helpdesk_ticket_ids = fields.One2many(comodel_name="helpdesk.ticket", inverse_name="partner_id", string="Related tickets")
    helpdesk_ticket_count = fields.Integer(compute="_compute_helpdesk_ticket_count", string="Ticket count")
    helpdesk_ticket_active_count = fields.Integer(compute="_compute_helpdesk_ticket_count", string="Ticket active count")
    helpdesk_ticket_count_string = fields.Char(compute="_compute_helpdesk_ticket_count", string="Tickets")
    helpdesk_level = fields.Selection(
        string='Helpdesk Level',
        selection=[('manager', "Manager"), ('user', "User")],
        default='user',
        help="Manager has the permission to access to all the client ticket",
        required=True
    )

    @api.model
    def create(self, vals):
        create_sequence = self.env['ir.sequence']
        res = super(Partner, self).create(vals)
        if res.company_type == 'company':
            dict_seq = {
                'name': 'Helpdesk Ticket',
                'code': 'helpdesk.ticket',
                'prefix': 'TICK/',
                'padding': 5,
                'partner_id': res.id,
                'company_id': self.env.company.id,
            }
            dict_seq['name'] += ' ' + res.name.split(' ')[0][:3].upper()
            dict_seq['code'] += '.' + res.name.split(' ')[0][:3].lower()
            dict_seq['prefix'] += res.name.split(' ')[0][:3].upper() + '/'
            if dict_seq:
                create_sequence.create(dict_seq)
        return res

    def _compute_helpdesk_ticket_count(self):
        for record in self:
            ticket_ids = self.env["helpdesk.ticket"].search([("partner_id", "child_of", record.id)])
            record.helpdesk_ticket_count = len(ticket_ids)
            record.helpdesk_ticket_active_count = len(ticket_ids.filtered(lambda ticket: not ticket.stage_id.closed))
            count_active = record.helpdesk_ticket_active_count
            count = record.helpdesk_ticket_count
            record.helpdesk_ticket_count_string = "{} / {}".format(count_active, count)

    def action_view_helpdesk_tickets(self):
        return {
            "name": self.name,
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "helpdesk.ticket",
            "type": "ir.actions.act_window",
            "domain": [("partner_id", "child_of", self.id)],
            "context": self.env.context,
        }


class User(models.Model):
    _inherit = 'res.users'

    def _get_my_tickets(self):
        for record in self:
            record.count_ticket = 0
            obj_ticket_ids = self.env['helpdesk.ticket'].search([('stage_id.closed', '=', False), ('user_id', '=', record.id)])
            if obj_ticket_ids:
                record.count_ticket = len(obj_ticket_ids)

    count_ticket = fields.Integer('Ticket by user', compute='_get_my_tickets')


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    partner_id = fields.Many2one('res.partner', 'Client')

