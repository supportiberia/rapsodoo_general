# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import _, http
from odoo.exceptions import AccessError
from odoo.http import request
from operator import itemgetter

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.tools import groupby as groupbyelem


class CustomerPortalHelpdesk(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        level = partner.helpdesk_level
        ticket_count = request.env["helpdesk.ticket"].search_count([("partner_id", "child_of", partner.id)])
        if level == 'manager':
            client = request.env.user.partner_id.parent_id.id
            ticket_count = request.env["helpdesk.ticket"].search_count([('client_id', '!=', False),
                                                                        ('client_id', '=', client)])
        values["ticket_count"] = ticket_count
        return values

    def _helpdesk_ticket_check_access(self, ticket_id):
        ticket = request.env["helpdesk.ticket"].browse([ticket_id])
        ticket_sudo = ticket.sudo()
        try:
            ticket.check_access_rights("read")
            ticket.check_access_rule("read")
        except AccessError:
            raise
        return ticket_sudo

    def _helpdesk_ticket_manager_access(self, ticket_id):
        ticket = request.env["helpdesk.ticket"].browse([ticket_id])
        ticket_sudo = ticket.sudo()
        return ticket_sudo

    @http.route(
        ["/my/tickets", "/my/tickets/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_tickets(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, groupby='none', **kw):
        values = self._prepare_portal_layout_values()
        _items_per_page = 80
        HelpdesTicket = request.env["helpdesk.ticket"]
        partner = request.env.user.partner_id
        level = partner.helpdesk_level
        client = request.env.user.partner_id.parent_id.id
        domain = [('client_id', '!=', False), ('client_id', '=', client)]
        if level == 'user':
            domain = [("partner_id", "child_of", partner.id)]
        searchbar_sortings = {
            "date": {"label": _("Newest"), "order": "create_date desc"},
            "name": {"label": _("Name"), "order": "name"},
            "stage": {"label": _("Stage"), "order": "stage_id"},
            "partner": {"label": _("Contact"), "order": "partner_id"},
            "update": {
                "label": _("Last Stage Update"),
                "order": "last_stage_update desc",
            },
        }
        searchbar_groupby = self._get_searchbar_groupby()

        env_stage = request.env["helpdesk.ticket.stage"].search([])
        filter_stage_open = env_stage.filtered(lambda e: not e.closed)
        filter_stage_closed = env_stage.filtered(lambda e: e.closed)
        searchbar_filters = {
            "all": {"label": _("All"), "domain": []},
            'open': {'label': _('Open'), 'domain': [("stage_id", "in", filter_stage_open.ids)]},
            'closed': {'label': _('Closed'), 'domain': [("stage_id", "in", filter_stage_closed.ids)]}
        }
        for stage in env_stage:
            searchbar_filters.update(
                {
                    str(stage.id): {
                        "label": stage.name,
                        "domain": [("stage_id", "=", stage.id)],
                    }
                }
            )

        # default sort by order
        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        # default filter by value
        if not filterby:
            filterby = "all"
        domain += searchbar_filters[filterby]["domain"]

        # count for pager
        ticket_count = HelpdesTicket.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/tickets",
            url_args={},
            total=ticket_count,
            page=page,
            step=_items_per_page,
        )
        # content according to pager and archive selected
        order = self._ticket_get_order(order, groupby)

        # content according to pager and archive selected
        tickets = HelpdesTicket.search(domain, order=order, limit=_items_per_page, offset=pager["offset"])

        groupby_mapping = self._ticket_get_groupby_mapping()
        group = groupby_mapping.get(groupby)
        if group:
            grouped_tickets = [HelpdesTicket.concat(*g) for k, g in groupbyelem(tickets, itemgetter(group))]
        else:
            grouped_tickets = [tickets]

        values.update(
            {
                "date": date_begin,
                "grouped_tickets": grouped_tickets,
                "tickets": tickets,
                "page_name": "ticket",
                "pager": pager,
                "default_url": "/my/tickets",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_groupby": searchbar_groupby,
                "groupby": groupby,
                "searchbar_filters": searchbar_filters,
                "filterby": filterby,
            }
        )
        return request.render("helpdesk_pro.portal_my_tickets", values)

    def _get_searchbar_groupby(self):
        values = {
            'none': {'input': 'none', 'label': _('None'), 'order': 1},
            'category': {'input': 'category', 'label': _('Type ticket'), 'order': 2},
            'module': {'input': 'module', 'label': _('Category'), 'order': 3},
            'stage': {'input': 'stage', 'label': _('Status'), 'order': 4},
            'contact': {'input': 'contact', 'label': _('Contact'), 'order': 7},
        }
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _ticket_get_groupby_mapping(self):
        return {
            'category': 'category_id',
            'module': 'modules_id',
            'stage': 'stage_id',
            'contact': 'partner_id',
        }

    def _ticket_get_order(self, order, groupby):
        groupby_mapping = self._ticket_get_groupby_mapping()
        field_name = groupby_mapping.get(groupby, '')
        if not field_name:
            return order
        return '%s, %s' % (field_name, order)


    @http.route(["/my/ticket/<int:ticket_id>"], type="http", website=True)
    def portal_my_ticket(self, ticket_id=None, **kw):
        partner = request.env.user.partner_id
        level = partner.helpdesk_level
        ticket_sudo = self._helpdesk_ticket_manager_access(ticket_id)
        if level == 'user':
            try:
                ticket_sudo = self._helpdesk_ticket_check_access(ticket_id)
            except AccessError:
                return request.redirect("/my")
        values = self._ticket_get_page_view_values(ticket_sudo, **kw)
        return request.render("helpdesk_pro.portal_helpdesk_ticket_page", values)

    def _ticket_get_page_view_values(self, ticket, **kwargs):
        closed_stages = request.env["helpdesk.ticket.stage"].search(
            [("closed", "=", True)]
        )
        values = {
            "page_name": "ticket",
            "ticket": ticket,
            "closed_stages": closed_stages,
        }

        if kwargs.get("error"):
            values["error"] = kwargs["error"]
        if kwargs.get("warning"):
            values["warning"] = kwargs["warning"]
        if kwargs.get("success"):
            values["success"] = kwargs["success"]

        return values
