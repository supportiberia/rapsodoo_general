from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, AccessError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


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

    def _get_default_team_id(self):
        return self.env["helpdesk.ticket.team"].search([], limit=1).id

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
    team_id = fields.Many2one(comodel_name="helpdesk.ticket.team", string="Team", default=_get_default_team_id)
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
    solution = fields.Html('Solution details / Notes')
    entry_date = fields.Date('Init date', default=fields.Date.context_today, tracking=True)
    end_date = fields.Date('Finish date', tracking=True)
    count_day = fields.Float('Duration (days)', help='Duration planned', tracking=True, compute='_check_duration_project')
    count_real_day = fields.Float('Duration real (days)', help='Duration real = duration planned - time waiting', tracking=True, compute='_check_duration_project')
    dedicated_time = fields.Float('Dedicated time (hrs)', help='Dedicated time = Hours by task', tracking=True, compute='_check_duration_project')
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
    check_tm = fields.Boolean('Fixed Project?', default=False)
    company_id = fields.Many2one(comodel_name="res.company", string="Company", default=lambda self: self.env.company)
    report_count_day = fields.Float('Report Duration (days)', help='Duration planned')
    report_count_real_day = fields.Float('Report Duration real', help='Duration real = duration planned - time waiting')
    report_dedicated_time = fields.Float('Report Dedicated time', help='Dedicated time = Hours by task')

    @api.model
    def create(self, vals):
        res = super(HelpdeskTicket, self).create(vals)
        list_follower = []
        if vals.get("number", "/") == "/":
            vals["color"] = 7
            res.number = self._prepare_ticket_number(res)
            if not res.project_id:
                res.set_project_id()
            if res.team_id and not res.user_id:
                res.set_user_id()
            if res.project_id and res.project_id.user_id:
                manager_id = res.project_id.user_id.partner_id
                list_follower.append(manager_id.id)
            if res.client_id and res.client_id.child_ids:
                for child in res.client_id.child_ids:
                    if child == res.partner_id:
                        list_follower.append(child.id)
                    if child.helpdesk_level == 'manager':
                        list_follower.append(child.id)
            res.message_subscribe(partner_ids=list_follower)
            mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.new_ticket_request_email_template')
            self._create_mail_begin(mail_template, res)
        return res

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

    def assign_to_me(self):
        self.write({"user_id": self.env.user.id})

    def set_project_id(self):
        obj_project_id = self.env['project.project'].search([('partner_id', '=', self.client_id.id)], limit=1)
        project_filter = obj_project_id.filtered(lambda e: e.count_hours != 0 and e.diff_hours != 0) if obj_project_id else False
        if project_filter:
            self.write({'project_id': project_filter.id})

    def set_user_id(self):
        if self.team_id and self.team_id.user_ids:
            member = self.team_id.user_id
            if self.team_id.type_assigned == 'equitable':
                list_users = [{'user': user, 'count_ticket': user.count_ticket} for user in self.team_id.user_ids]
                val_min = min(list_users, key=lambda x: x['count_ticket'])
                member = val_min['user'] if val_min else self.team_id.user_ids[0]
            self.write({'user_id': member.id})

    def compose_email_message(self, ticket):
        obj_partner_id = self.env['res.partner'].search([('name', 'like', 'Admin')], limit=1)
        email_from = obj_partner_id.email if obj_partner_id else 'admin@email.com'
        email_to = ticket.partner_id.email if ticket.partner_id else 'user@email.com'
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
            msg_id = self.env['mail.mail'].sudo().create(values)
            if msg_id:
                msg_id.send()
        return True

    def get_portal_url(self):
        pass

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if "number" not in default:
            default["number"] = self._prepare_ticket_number(default)
        res = super(HelpdeskTicket, self).copy_data(default=default)[0]
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

    def _prepare_ticket_number(self, res):
        seq = self.env["ir.sequence"].search([('code', 'like', 'helpdesk')])
        if not seq:
            raise ValidationError(_("The company has not sequence assigne. Please contact with the Admin"))
        if res.client_id:
            seq = seq.filtered(lambda e: e.partner_id.id == res.client_id.id)
            if not seq:
                raise ValidationError(_("Sorry!! You have not permission for this operation. \n "
                                        "There are not sequence related to your company."
                                        " Please contact with the Admin"))
            elif res.company_id:
                seq = seq.with_company(res.company_id.id)
        return seq[0].next_by_code(seq.code) or "/"

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
        self.ensure_one()
        # Getting the existing task related with the ticket
        task = self.env['project.task'].search([('ticket_id', '=', self.id)])
        action = self.env['ir.actions.actions']._for_xml_id('project.action_view_all_task')
        form_view = [(self.env.ref('project.view_task_form2').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
        else:
            action['views'] = form_view
        if len(task) == 1:
            # If exist a task related
            # Call the form with the data charged
            action['domain'] = [('ticket_id', '=', self.id)]
            action['res_id'] = task.ids[0]
            action['context'] = {'create': False}
        if not task:
            # If not exist the any task related
            # Charge the form with some values as default
            action['context'] = {'default_ticket_id': self.id,
                                 'default_project_id': self.project_id.id,
                                 'default_partner_id': self.client_id.id}
        return action

    def general_update(self, record):
        dict_wait = {
            'user_id': self.user_id.id,
            'end_date': datetime.now(),
        }
        obj_waiting = self.env['detail.waiting.days'].search([('end_date', '=', False)], limit=1)
        if obj_waiting:
            obj_waiting.sudo().write(dict_wait)

    def check_project_related(self):
        for record in self:
            if not record.check_tm and not record.project_id:
                raise UserError(_("Project is required to work on this ticket.\nCreate a project "
                                  "or contact an Administrator."))
            else:
                return True

    def check_task_related(self):
        for record in self:
            if not record.check_tm and not record.task_id:
                raise UserError(_("Task is required to resolve or close work on this ticket.\nCreate a task "
                                  "or contact an Administrator."))
            else:
                return True

    def assign_ticket_draft(self):
        for record in self:
            ok_project = self.check_project_related()
            if ok_project:
                dict_update_f = {
                    'check_working': False,
                    'check_waiting': False,
                    'check_resolved': False,
                    'check_cancel': False,
                    'check_email': False,
                    'check_task': False,
                    'kanban_state': 'normal',
                    'color': 7

                }
                record.sudo().write(dict_update_f)
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'new')], limit=1)
                if obj_stage:
                    record.sudo().write({'stage_id': obj_stage.id, 'end_date': datetime.now()})

    def assign_ticket_working(self):
        for record in self:
            ok_project = self.check_project_related()
            if ok_project:
                dict_update_f = {
                    'check_working': True,
                    'check_waiting': False,
                    'check_resolved': False,
                    'check_cancel': False,
                    'check_email': False,
                    'check_task': True,
                    'kanban_state': 'normal',
                    'color': 4

                }
                record.sudo().write(dict_update_f)
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'pro')], limit=1)
                if obj_stage:
                    record.sudo().write({'stage_id': obj_stage.id, 'end_date': datetime.now()})
                    self.general_update(record)
                    mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.process_ticket_request_email_template')
                    record._create_mail_begin(mail_template, record)

    def assign_ticket_waiting(self):
        ok_project = self.check_project_related()
        ok_task = self.check_task_related()
        if ok_project and ok_task:
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
                record.color = 15
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'can')], limit=1)
                if obj_stage:
                    record.stage_id = obj_stage.id
                    record.end_date = datetime.now()
                    self.general_update(record)
                    mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.closed_ticket_template')
                    record._create_mail_begin(mail_template, record)

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
                record.color = 10
                obj_stage = self.env['helpdesk.ticket.stage'].search([('key_stage', '=', 'don')], limit=1)
                if obj_stage:
                    record.stage_id = obj_stage.id
                    record.end_date = datetime.now()
                    self.general_update(record)
                    mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.closed_ticket_template')
                    record._create_mail_begin(mail_template, record)

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
            if record.task_id:
                list_task = [task for task in record.task_id.child_ids]
                list_task.append(record.task_id)
                record.dedicated_time = sum(task.effective_hours for task in list_task)

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

    @api.constrains('stage_id', 'dedicated_time', 'count_real_day', 'count_day')
    def _check_values_report(self):
        for record in self:
            record.report_count_day = record.count_day
            record.report_count_real_day = record.count_real_day
            record.report_dedicated_time = record.dedicated_time

    @api.model
    def update_state(self):
        tickets = self.search([('check_working', '=', True)])
        for ticket in tickets:
            if ticket.mapped('team_id'):
                val_days = ticket.mapped('team_id').response_time
                val_update_days = ticket.last_stage_update.date() + relativedelta(days=val_days)
                if date.today() == val_update_days:
                    end_date = val_update_days + relativedelta(days=1)
                    ticket.activity_schedule('mail.mail_activity_data_todo', end_date,
                                               _("The ticket %s takes %s days in 'In Progress'.", ticket.number, val_days),
                                       user_id=ticket.user_id.id or self.env.uid)
                    # mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.notification_email_progress_ticket_template')
                    # self._create_mail_begin(mail_template, ticket)


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
                mail_template = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_pro.waiting_ticket_request_email_template')
                obj_ticket._create_mail_begin(mail_template, obj_ticket)
        return super(MailComposeMessage, self)._action_send_mail(auto_commit=auto_commit)


class Message(models.Model):
    _inherit = 'mail.message'

    def create(self, vals_list):
        res = super(Message, self).create(vals_list)
        if res:
            obj_ticket = self.env['helpdesk.ticket'].search([('id', '=', res.res_id),
                                                             ('partner_id', '=', res.author_id.id),
                                                             ('stage_id.key_stage', '=', 'wai'), ('color', '=', 1)], limit=1)
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

    @api.constrains('count_hours')
    def _check_count_hours(self):
        for record in self:
            if record.count_hours:
                record.name = record.name.split(' ')[:1][0]
                record.name = record.name + ' support pack - ' + str(record.count_hours) + ' hrs'


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
        request = super(Task, self).create(vals)
        request.ticket_id.task_id = request.id
        # Verify if already exist a task related with the same ticket
        task = self.search_count([('ticket_id', '=', request.ticket_id.id), ('ticket_id', '!=', False)])
        if task > 1:
            raise ValidationError(_('Sorry only can be 1 task related with each ticket'))
        return request

    @api.onchange('timesheet_ids')
    def onchange_timesheet_ids(self):
        if self.timesheet_ids and self.project_id:
            self.planned_hours = self.project_id.diff_hours
