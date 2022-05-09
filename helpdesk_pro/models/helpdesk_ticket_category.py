from odoo import fields, models


class HelpdeskCategory(models.Model):
    _name = "helpdesk.ticket.category"
    _description = "Helpdesk Ticket Category"

    active = fields.Boolean(string="Active",default=True)
    name = fields.Char(string="Name", required=True, translate=True)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company)


class HelpdeskTicketUrgency(models.Model):
    _name = "helpdesk.ticket.urgency"
    _description = "Helpdesk Ticket Urgency"

    active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string="Name", required=True, translate=True)
    key_name = fields.Char(string="Key")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company)


class HelpdeskTicketModule(models.Model):
    _name = "helpdesk.ticket.module"
    _description = "Helpdesk Ticket Module"

    active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string="Name", required=True, translate=True)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company)
    partner_ids = fields.Many2many('res.partner', 'rel_module_partner', 'module_id', 'partner_id', 'Clients')


class HelpdeskTicketEnvironment(models.Model):
    _name = "helpdesk.ticket.environment"
    _description = "Helpdesk Ticket Environment"

    active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string="Name", required=True, translate=True)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company)
