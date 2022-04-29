from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, AccessError
from datetime import datetime, timedelta, date


TICKET_PRIORITY_U = [
    ('3', 'Low priority'),
    ('2', 'Medium priority'),
    ('1', 'High priority'),
    ('0', 'Critical'),
]


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _rec_name = "number"
    _order = "number desc"
    _mail_post_access = "read"
    _inherit = ["mail.thread.cc", "mail.activity.mixin"]

    def _get_default_stage_id(self):
        return self.env["helpdesk.ticket.stage"].search([], limit=1).id

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        stage_ids = self.env["helpdesk.ticket.stage"].search([])
        return stage_ids

    number = fields.Char(string="Ticket number", default="/", readonly=True)
    name = fields.Char(string="Title", required=True)
    description = fields.Html(required=True, sanitize_style=True)
    user_id = fields.Many2one(comodel_name="res.users", string="Assigned user", tracking=True, index=True)
    user_ids = fields.Many2many(comodel_name="res.users", related="team_id.user_ids", string="Users")
    stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Stage",
        group_expand="_read_group_stage_ids",
        default=_get_default_stage_id,
        tracking=True,
        ondelete="restrict",
        index=True,
        copy=False,
    )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Contact")
    partner_name = fields.Char()
    partner_email = fields.Char(string="Email")
    last_stage_update = fields.Datetime(string="Last Stage Update", default=fields.Datetime.now)
    assigned_date = fields.Datetime(string="Assigned Date")
    closed_date = fields.Datetime(string="Closed Date")
    closed = fields.Boolean(related="stage_id.closed")
    unattended = fields.Boolean(related="stage_id.unattended", store=True)
    tag_ids = fields.Many2many(comodel_name="helpdesk.ticket.tag", string="Tags")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", required=True, default=lambda self: self.env.company)
    channel_id = fields.Many2one(
        comodel_name="helpdesk.ticket.channel",
        string="Channel",
        help="Channel indicates where the source of a ticket"
             "comes from (it could be a phone call, an email...)",
    )
    category_id = fields.Many2one(comodel_name="helpdesk.ticket.category", string="Ticket type")
    team_id = fields.Many2one(comodel_name="helpdesk.ticket.team", string="Team")
    priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        string="Priority", default="1")
    attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "helpdesk.ticket")],
        string="Media Attachments")
    color = fields.Integer(string="Color Index")
    kanban_state = fields.Selection(
        selection=[
            ("normal", "Default"),
            ("done", "Ready for next stage"),
            ("blocked", "Blocked"),
        ], string="Kanban State")
    active = fields.Boolean(default=True)
    type_urgency = fields.Many2one('helpdesk.ticket.urgency', string='Priority (Client)')
    type_impact = fields.Selection(TICKET_PRIORITY_U, string='Priority (User)')
    client_id = fields.Many2one('res.partner', string='Client', help='Select client company to assigned this ticket')
    solution = fields.Html('Solution Obs')
    entry_date = fields.Date('Init date', default=fields.Date.context_today, tracking=True)
    end_date = fields.Date('Finish date', tracking=True)
    count_day = fields.Float('Duration (days)', help='Duration planned', tracking=True, compute='_check_duration_project')
    count_real_day = fields.Float('Duration real', help='Duration real = duration planned - time waiting', tracking=True, compute='_check_duration_project')
    dedicated_time = fields.Float('Dedicated time', help='Dedicated time = Working hours * days', tracking=True, compute='_check_duration_project')
    environment = fields.Many2one('helpdesk.ticket.environment', string='Environment')
    git_link = fields.Char('Git Link')
    url_link = fields.Char('Environment Link')
    check_01_name = fields.Char("Attachment")
    check_01 = fields.Binary(string='Attachments', copy=False, help='Additional attachments')
    modules_id = fields.Many2one('helpdesk.ticket.module', string='Category')
    check_working = fields.Boolean('Working', default=False)
    check_waiting = fields.Boolean('Waiting', default=False)
    check_resolved = fields.Boolean('Resolved', default=False)
    check_cancel = fields.Boolean('Cancel', default=False)
    check_email = fields.Boolean('Send email?', default=False)
    check_task = fields.Boolean('Create task?', default=False)
    project_id = fields.Many2one('project.project', 'Project')
    task_id = fields.Many2one('project.task', 'Task')
    project_count = fields.Integer(compute='_compute_project_task', string="Number of Project")
    task_count = fields.Integer(compute='_compute_project_task', string="Number of Task")
    resource_calendar_id = fields.Many2one('resource.calendar', 'Working Hours', related='team_id.resource_calendar_id', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    check_tm = fields.Boolean('TM Project?', default=False)

    def assign_to_me(self):
        self.write({"user_id": self.env.user.id})

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_name = self.partner_id.name
            self.partner_email = self.partner_id.email

    @api.onchange("team_id", "user_id")
    def _onchange_dominion_user_id(self):
        if self.user_id and self.user_ids and self.user_id not in self.team_id.user_ids:
            self.update({"user_id": False})
            return {"domain": {"user_id": []}}
        if self.team_id:
            return {"domain": {"user_id": [("id", "in", self.user_ids.ids)]}}
        else:
            return {"domain": {"user_id": []}}

    @api.model
    def create(self, vals):
        if vals.get("number", "/") == "/":
            vals["number"] = self._prepare_ticket_number(vals)
            res = super(HelpdeskTicket, self).create(vals)
            mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.new_ticket_request_email_template')
            self._create_mail_begin(mail_template, res)
            # add equipo y assigned
        return res

    def compose_email_message(self, ticket):
        body_message = 'mensaje mensaje'
        obj_partner_id = self.env['res.partner'].search([('name', 'like', 'Admin')], limit=1)
        email_from = obj_partner_id.email if obj_partner_id else 'admin@email.com'
        email_to = ticket.partner_id.email if ticket.partner_id else 'user@email.com'
        author_id = obj_partner_id.id
        subtype_id = self.env["ir.model.data"]._xmlid_to_res_id('mail.mt_comment')
        mail_data = {
            'email_from': email_from,
            'email_to': email_to,
            'res_id': ticket.id
        }
        return mail_data

    def _create_mail_begin(self, template, ticket):
        template_browse = self.env['mail.template'].browse(template)
        data_compose = self.compose_email_message(ticket)
        if template_browse and data_compose:
            values = template_browse.generate_email(ticket.id, ['subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'reply_to'])
            values['email_to'] = data_compose['email_to']
            values['email_from'] = data_compose['email_from']
            values['reply_to'] = data_compose['email_from']
            values['res_id'] = data_compose['res_id']
            mail_mail_obj = self.env['mail.mail']
            msg_id = self.env['mail.mail'].sudo().create(values)
            if msg_id:
                mail_mail_obj.send(msg_id)
        return True

    def get_portal_url(self):
        return

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if "number" not in default:
            default["number"] = self._prepare_ticket_number(default)
        res = super().copy(default)
        return res

    def write(self, vals):
        for _ticket in self:
            now = fields.Datetime.now()
            if vals.get("stage_id"):
                stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
                vals["last_stage_update"] = now
                if stage.closed:
                    vals["closed_date"] = now
            if vals.get("user_id"):
                vals["assigned_date"] = now
        return super().write(vals)

    def action_duplicate_tickets(self):
        for ticket in self.browse(self.env.context["active_ids"]):
            ticket.copy()

    @api.constrains('stage_id')
    def _onchange_stage_id(self):
        project_filter = False
        for record in self:
            if not record.project_id:
                obj_project_id = self.env['project.project'].search([('partner_id', '=', record.client_id.id)], limit=1)
                project_filter = obj_project_id.filtered(lambda e: e.count_hours != 0 and e.count_hours == e.diff_hours) if obj_project_id else False
            if project_filter:
                record.project_id = project_filter.id

    def _prepare_ticket_number(self, values):
        seq = self.env["ir.sequence"]
        if "company_id" in values:
            seq = seq.with_company(values["company_id"])
        return seq.next_by_code("helpdesk.ticket.sequence") or "/"

    def _track_template(self, tracking):
        res = super()._track_template(tracking)
        ticket = self[0]
        if "stage_id" in tracking and ticket.stage_id.mail_template_id:
            res["stage_id"] = (
                ticket.stage_id.mail_template_id,
                {
                    "auto_delete_message": True,
                    "subtype_id": self.env["ir.model.data"]._xmlid_to_res_id("mail.mt_note"),
                    "email_layout_xmlid": "mail.mail_notification_light",
                },
            )
        return res

    @api.model
    def message_new(self, msg, custom_values=None):
        """Override message_new from mail gateway so we can set correct
        default values.
        """
        if custom_values is None:
            custom_values = {}
        defaults = {
            "name": msg.get("subject") or _("No Subject"),
            "description": msg.get("body"),
            "partner_email": msg.get("from"),
            "partner_id": msg.get("author_id"),
        }
        defaults.update(custom_values)

        # Write default values coming from msg
        ticket = super().message_new(msg, custom_values=defaults)

        # Use mail gateway tools to search for partners to subscribe
        email_list = tools.email_split(
            (msg.get("to") or "") + "," + (msg.get("cc") or "")
        )
        partner_ids = [
            p.id
            for p in self.env["mail.thread"]._mail_find_partner_from_emails(
                email_list, records=ticket, force_create=False
            )
            if p
        ]
        ticket.message_subscribe(partner_ids)

        return ticket

    def message_update(self, msg, update_vals=None):
        """ Override message_update to subscribe partners """
        email_list = tools.email_split(
            (msg.get("to") or "") + "," + (msg.get("cc") or "")
        )
        partner_ids = [
            p.id
            for p in self.env["mail.thread"]._mail_find_partner_from_emails(
                email_list, records=self, force_create=False
            )
            if p
        ]
        self.message_subscribe(partner_ids)
        return super().message_update(msg, update_vals=update_vals)

    def _message_get_suggested_recipients(self):
        recipients = super()._message_get_suggested_recipients()
        try:
            for ticket in self:
                if ticket.partner_id:
                    ticket._message_add_suggested_recipient(
                        recipients, partner=ticket.partner_id, reason=_("Customer")
                    )
                elif ticket.partner_email:
                    ticket._message_add_suggested_recipient(
                        recipients,
                        email=ticket.partner_email,
                        reason=_("Customer Email"),
                    )
        except AccessError:
            # no read access rights -> just ignore suggested recipients because this
            # imply modifying followers
            pass
        return recipients

    @api.depends('project_id', 'task_id')
    def _compute_project_task(self):
        for record in self:
            record.project_count = 0
            record.task_count = 0
            if record.project_id:
                record.project_count = 1
            if record.task_id:
                record.task_count = 1

    def action_open_project(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project',
            'res_model': 'project.project',
            'view_mode': 'tree,kanban,form',
            'domain': [('partner_id', '=', self.client_id.id)],
            'context': ({'default_partner_id': self.client_id.id,
                         'default_name': 'Project: ' + self.client_id.name})
        }

    def action_open_task(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Task',
            'res_model': 'project.task',
            'view_mode': 'tree,kanban,form',
            'domain': [('id', '=', self.task_id.id)],
            'context': ({'default_project_id': self.project_id.id,
                         'default_partner_id': self.client_id.id})
        }

    def general_update(self, record):
        dict_wait = {
            'user_id': self.user_id.id,
            'end_date': datetime.now(),
        }
        obj_waiting = self.env['detail.waiting.days'].search([('end_date', '=', False)], limit=1)
        if obj_waiting:
            obj_waiting.write(dict_wait)
            # record.message_post(body=_("Update time waiting: %s") % obj_waiting.name)

    def check_project_related(self):
        for record in self:
            if record.check_tm and not record.project_id:
                raise UserError(_("Project is required to work on this ticket.\nCreate a project "
                                  "or contact an Administrator."))
            else:
                return True

    def check_task_related(self):
        for record in self:
            if record.check_tm and not record.task_id:
                raise UserError(_("Task is required to resolve or close work on this ticket.\nCreate a task "
                                  "or contact an Administrator."))
            else:
                return True

    def assign_ticket_working(self):
        for record in self:
            ok_project = self.check_project_related()
            if ok_project:
                record.check_working = True
                record.check_waiting = False
                record.check_resolved = False
                record.check_cancel = False
                record.check_email = False
                record.check_task = True
                record.kanban_state = 'normal'
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'pro')], limit=1)
                if obj_stage:
                    record.stage_id = obj_stage.id
                    record.end_date = datetime.now()
                    self.general_update(record)

    def assign_ticket_waiting(self):
        ok_project = self.check_project_related()
        if ok_project:
            ctx = {
                'default_model': 'helpdesk.ticket',
                'default_res_id': self.ids[0],
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'force_email': True,
                'mail_ticket': 'ticket',
            }
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(False, 'form')],
                'view_id': False,
                'target': 'new',
                'context': ctx,
            }

    def assign_ticket_cancel(self):
        for record in self:
            ok_task = self.check_task_related()
            if ok_task:
                record.check_cancel = True
                record.check_working = True
                record.check_waiting = True
                record.check_resolved = True
                record.check_email = False
                record.check_task = True
                record.kanban_state = 'done'
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'can')], limit=1)
                if obj_stage:
                    record.stage_id = obj_stage.id
                    record.end_date = datetime.now()
                    self.general_update(record)

    def assign_ticket_resolved(self):
        for record in self:
            ok_task = self.check_task_related()
            if ok_task:
                record.check_resolved = True
                record.check_working = True
                record.check_waiting = True
                record.check_cancel = False
                record.check_email = False
                record.check_task = True
                record.kanban_state = 'done'
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'don')], limit=1)
                if obj_stage:
                    record.stage_id = obj_stage.id
                    record.end_date = datetime.now()
                    self.general_update(record)

    @api.depends('entry_date', 'end_date')
    def _check_duration_project(self):
        for record in self:
            record.count_day = 0
            record.count_real_day = 0
            record.dedicated_time = 0
            val_waiting = 0
            count_w = 0
            obj_waiting_ids = self.env['detail.waiting.days'].search([('ticket_id', '=', record.id)])
            if record.entry_date and record.end_date:
                period = 1
                date_sum = record.end_date + timedelta(days=period)
                temp_count_day = (date_sum - record.entry_date).days
                obj_check_w = self.check_weekend(record.end_date, record.entry_date)
                if obj_check_w:
                    count_w = obj_check_w
                record.count_day = temp_count_day - count_w
            list_wait = [obj_wait for obj_wait in obj_waiting_ids.mapped('count_day')]
            for val_w in list_wait:
                val_waiting += val_w
            record.count_real_day = record.count_day - val_waiting

    def check_weekend(self, end_date, entry_date):
        count_w = 0
        list_dates = [entry_date + timedelta(days=d) for d in
                      range((end_date - entry_date).days + 1)]
        if list_dates:
            for item in list_dates:
                if item.weekday() in [5, 6]:
                    count_w += 1
        return count_w

    @api.depends('partner_id')
    @api.onchange('partner_id')
    def onchange_client_id(self):
        for record in self:
            record.client_id = record.partner_id.parent_id.id if record.partner_id.parent_id else False

    @api.constrains('partner_id')
    def check_client_id(self):
        for record in self:
            if not record.client_id:
                record.client_id = record.partner_id.parent_id.id if record.partner_id.parent_id else False

    @api.constrains('type_urgency', 'type_impact')
    def check_priority(self):
        for record in self:
            if record.type_urgency and record.type_impact:
                cross_id = self.env['cross.ticket'].search([('type_urgency', '=', record.type_urgency.key_name),
                                                            ('type_impact', '=', record.type_impact)], limit=1)
                if cross_id:
                    record.priority = str(cross_id.cross_impact)

    def action_open_detail_days(self):
        action = self.env['ir.actions.act_window']._for_xml_id('helpdesk_pro.detail_days_wizard_action')
        obj_waiting_ids = self.env['detail.waiting.days'].search([('ticket_id', '=', self.id)])
        ctx = ({'default_report_lines': obj_waiting_ids.ids})
        action['context'] = ctx
        return action


class CrossTicket(models.Model):
    _name = 'cross.ticket'
    _description = 'Cross Ticket'
    _rec_name = 'type_urgency'

    type_urgency = fields.Selection(TICKET_PRIORITY_U, string='Priority (Client)')
    type_impact = fields.Selection(TICKET_PRIORITY_U, string='Priority (User)')
    cross_impact = fields.Integer('Cross value',
                                  help='0 - Low priority \n  1 - Medium priority \n 2 - High priority \n 3 - Critical')


class DetailWaitingDays(models.Model):
    _name = 'detail.waiting.days'
    _description = 'Detail Waiting Days'

    name = fields.Char('Name', index=True, required=True, default='/')
    user_id = fields.Many2one('res.users', 'User', readonly=True)
    ticket_id = fields.Many2one('helpdesk.ticket', 'Ticket')
    entry_date = fields.Date('Init date')
    end_date = fields.Date('Finish date')
    count_day = fields.Float('Count (-)')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('detail.waiting.days')
        request = super(DetailWaitingDays, self).create(vals)
        return request

    @api.constrains('end_date')
    def onchange_report_lines(self):
        for record in self:
            count_w = 0
            if record.entry_date and record.end_date:
                temp_count_day = (record.end_date - record.entry_date).days
                obj_check_w = self.check_weekend(record.end_date, record.entry_date)
                if obj_check_w:
                    count_w = obj_check_w
                record.count_day = temp_count_day - count_w

    def check_weekend(self, end_date, entry_date):
        count_w = 0
        list_dates = [entry_date + timedelta(days=d) for d in
                      range((end_date - entry_date).days + 1)]
        if list_dates:
            for item in list_dates:
                if item.weekday() in [5, 6]:
                    count_w += 1
        return count_w


class DetailDays(models.TransientModel):
    _name = 'detail.days'
    _description = 'Detail Days'
    _rec_name = 'report_lines'

    report_lines = fields.Many2many('detail.waiting.days', 'rel_detail_day_waiting', 'day_id', 'waiting_id', 'Detail Waiting Days')


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        self.ensure_one()
        context = self._context
        if context.get('default_res_id') and context.get('mail_ticket'):
            obj_ticket = self.env['helpdesk.ticket'].search([('id', '=', context.get('default_res_id'))], limit=1)
            if obj_ticket:
                dict_wait = {
                    'user_id': self._uid,
                    'ticket_id': obj_ticket.id,
                    'entry_date': datetime.now(),
                }
                obj_ticket.check_waiting = True
                obj_ticket.check_working = False
                obj_ticket.check_resolved = False
                obj_ticket.check_cancel = False
                obj_ticket.check_email = True
                obj_ticket.check_task = False
                obj_ticket.kanban_state = 'blocked'
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'wai')], limit=1)
                if obj_stage:
                    obj_ticket.stage_id = obj_stage.id
                obj_ticket.end_date = datetime.now()
                if not any(self.env['detail.waiting.days'].search([('end_date', '=', False)])):
                    create_waiting = self.env['detail.waiting.days'].create(dict_wait)
                    if create_waiting:
                        obj_ticket.message_post(body=_("Created time waiting: %s") % create_waiting.name)
        return super(MailComposeMessage, self)._action_send_mail(auto_commit=auto_commit)


class Message(models.Model):
    _inherit = 'mail.message'

    def create(self, vals_list):
        res = super(Message, self).create(vals_list)
        if res:
            obj_ticket = self.env['helpdesk.ticket'].search([('id', '=', res.res_id),
                                                             ('partner_id', '=', res.author_id.id),
                                                             ('stage_id.key_stage', '=', 'wai')], limit=1)
            if obj_ticket:
                obj_ticket.assign_ticket_working()
        return res


class Project(models.Model):
    _inherit = "project.project"

    count_hours = fields.Float('Pack', help='Pack Support (hours)')
    diff_hours = fields.Float('Diff.', compute='_call_diff_hours', help='Difference (Pack´s hours - hours spent)')
    ticket_ids = fields.One2many('helpdesk.ticket', 'project_id', 'Ticket')

    @api.model
    def create(self, vals):
        request = super(Project, self).create(vals)
        if request.name:
            request.name = request.name + '´s support pack - ' + str(request.count_hours) + 'hrs'
        if request._context.get('active_id'):
            obj_ticket = self.env['helpdesk.ticket'].search([('id', '=', request._context.get('active_id'))], limit=1)
            if obj_ticket:
                obj_ticket.project_id = request.id
        return request

    @api.depends('count_hours', 'name')
    def _call_diff_hours(self):
        for record in self:
            record.diff_hours = 0
            val_total = 0
            list_all = []
            if record.count_hours:
                obj_task_ids = self.env['project.task'].search([('project_id', '=', record.id)])
                if obj_task_ids:
                    for obj_task in obj_task_ids:
                        list_all += obj_task.timesheet_ids.mapped('unit_amount')
                if list_all:
                    for val_all in list_all:
                        val_total += val_all
                record.diff_hours = record.count_hours - val_total


class Task(models.Model):
    _inherit = "project.task"

    def _call_planned_hours(self):
        obj_project = self.env['project.project'].search([('id', '=', self._context.get('default_project_id'))], limit=1)
        if obj_project:
            if obj_project.diff_hours != 0:
                return obj_project.diff_hours
            else:
                return obj_project.count_hours

    ticket_id = fields.Many2one('helpdesk.ticket', 'Ticket')
    planned_hours = fields.Float("Initially Planned Hours",
                                 help='Time planned to achieve this task (including its sub-tasks).', tracking=True,
                                 default=lambda self: self._call_planned_hours())

    @api.model
    def create(self, vals):
        ticket_id = False
        request = super(Task, self).create(vals)
        if len([ticket.task_id for ticket in request.project_id.ticket_ids]) <= 1:
            if request._context.get('active_model') == 'project.project':
                ticket_ids = [ticket.id for ticket in request.project_id.ticket_ids if not ticket.task_id] if request.project_id.ticket_ids else False
                if ticket_ids:
                    ticket_id = ticket_ids[0]
            if request._context.get('active_model') == 'helpdesk.ticket':
                ticket_id = request._context.get('active_id')
        obj_ticket = self.env['helpdesk.ticket'].search([('id', '=', ticket_id), ('task_id', '=', False)], limit=1)
        if obj_ticket:
            obj_ticket.task_id = request.id
        return request

