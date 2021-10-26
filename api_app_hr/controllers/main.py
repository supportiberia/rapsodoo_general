import requests
import json

from odoo import models
from odoo import http, _, exceptions
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)

version = "v1"
# clave api test
# 51b6d9c8b094f1ada742753691936798d01ff838


class User(http.Controller):

    @classmethod
    def auth_method_my_api_key(self):
        api_key = request.httprequest.headers.get("Authorization")
        if not api_key:
            return '{"status": 400, "response": "Error", "message": "Authorization header with API key missing"}'
        user_id = request.env["res.users.apikeys"]._check_credentials(scope="rpc", key=api_key)
        if not user_id:
            return '{"status": 400, "response": "Error", "message": "API key invalid"}'
        else:
            return '{"status": 200, "response": "Success", "message": "API key valid"}'

    # /hr_app/api/v1/users/search
    @http.route('/hr_app/api/' + version + '/users/search', auth="public", methods=['GET'], csrf=False, type='json', cors="*")
    def search(self, **kw):
        try:
            # Validación de la api-key
            # api_key_valid = User.auth_method_my_api_key()
            # api_key_valid = json.loads(api_key_valid)
            # if api_key_valid["status"] != 200:
            #     return json.dumps(api_key_valid)
            # else:
            # Query
            query = [('active', '=', True)]
            get_users = http.request.env["res.users"].sudo().search(query)
            if not get_users:
                return {"status": 404, "response": [], "message": "No existe el usuario"}
            users = []
            for user in get_users:
                vals = {
                    "Id": user.id,
                    "Login": user.login,
                    "Partner": user.partner_id.id,
                    "Nombre Partner": user.partner_id.name,
                    "Ciudad": user.partner_id.city,
                    "Provincia": user.partner_id.state_id.name,
                    "Telefono": user.partner_id.mobile,
                    "Notification": user.notification_type,
                }
            users.append(vals)
        except Exception as e:
            raise Exception(e)
        return {'status': 200, 'response': users, 'message': 'Usuarios recuperados correctamente'}

    # /hr_app/api/v1/user/get
    @http.route('/hr_app/api/' + version + '/user/get', auth="public", methods=['GET'], csrf=False, type='json', cors="*")
    def get(self, **kw):
        try:
            # api_key_valid = User.auth_method_my_api_key()
            # api_key_valid = json.loads(api_key_valid)
            # if api_key_valid["status"] != 200:
            #     return json.dumps(api_key_valid)
            # else:
            data = {
                "status": "",
                "response": [],
                "message": "",
            }
            vals = {
                "Id": "",
                "Login": "",
                "Partner": "",
                "Nombre": "",
                "Genero": "",
                "Ciudad": "",
                "Provincia": "",
                "Telefono": "",
                "Notification": "",
                "Nivel": "",
                "Campo": "",
                "Study": "",
                "Experiencia": [],
                "Habilidades": [],
            }
            email = request.jsonrequest['params']['login']
            query = [('login', '=', email), ('active', '=', True)]
            get_user = http.request.env["res.users"].sudo().search(query)
            if not get_user:
                data['status'] = 404
                data['message'] = 'No existe usuario'
                return data
            users = []
            for user in get_user:
                employee_ids = User.get_employee(user, vals)
                if employee_ids:
                    _logger.info('<<Load info del Employee>>')
                vals["Id"] = user.id
                vals["Login"] = user.login
                vals["Partner"] = user.partner_id.id
                vals["Nombre"] = user.partner_id.name
                vals["Ciudad"] = user.partner_id.city
                vals["Provincia"] = user.partner_id.state_id.name
                vals["Telefono"] = user.partner_id.mobile
                vals["Notification"] = user.notification_type
            users.append(vals)
            data['status'] = 200
            data['response'] = users
            data['message'] = 'Usuario recuperado correctamente'
        except Exception as e:
            raise Exception(e)
        return data

    # /hr_app/api/v1/experiences/get
    @http.route('/hr_app/api/' + version + '/experiences/get', auth="public", methods=['GET'], csrf=False, type='json', cors="*")
    def get_experiences(self, **kw):
        try:
            data = {
                "status": "",
                "response": [],
                "message": "",
            }
            vals = {
                "Experiencia": []
            }
            email = request.jsonrequest['params']['login']
            query = [('login', '=', email), ('active', '=', True)]
            get_user = http.request.env["res.users"].sudo().search(query)
            if not get_user:
                data['status'] = 404
                data['message'] = 'No existe usuario'
                return data
            experiences = []
            for user in get_user:
                obj_employee = http.request.env["hr.employee"].sudo().search([('user_id', '=', user.id)])
                if obj_employee:
                    for employee in obj_employee:
                        if employee.resume_line_ids:
                            all_experiences = employee.resume_line_ids
                            experience_ids = User.get_experience(all_experiences, vals)
                            if experience_ids:
                                experiences.append(experience_ids)
                                data['status'] = 200
                                data['response'] = experiences
            data['message'] = 'Experiencias recuperadas correctamente'
        except Exception as e:
            raise Exception(e)
        return data

    # /hr_app/api/v1/skills/get
    @http.route('/hr_app/api/' + version + '/skills/get', auth="public", methods=['GET'], csrf=False, type='json', cors="*")
    def get_skills(self, **kw):
        try:
            data = {
                "status": "",
                "response": [],
                "message": "",
            }
            vals = {
                "Habilidades": []
            }
            email = request.jsonrequest['params']['login']
            query = [('login', '=', email), ('active', '=', True)]
            get_user = http.request.env["res.users"].sudo().search(query)
            if not get_user:
                data['status'] = 404
                data['message'] = 'No existe usuario'
                return data
            experiences = []
            for user in get_user:
                obj_employee = http.request.env["hr.employee"].sudo().search([('user_id', '=', user.id)])
                if obj_employee:
                    for employee in obj_employee:
                        if employee.employee_skill_ids:
                            all_skills = employee.employee_skill_ids
                            skill_ids = User.get_skills(all_skills, vals)
                            if skill_ids:
                                experiences.append(skill_ids)
                                data['status'] = 200
                                data['response'] = experiences
            data['message'] = 'Habilidades recuperadas correctamente'
        except Exception as e:
            raise Exception(e)
        return data

    @classmethod
    def get_employee(self, user, vals):
        obj_employee = http.request.env["hr.employee"].sudo().search([('user_id', '=', user.id)])
        if obj_employee:
            for employee in obj_employee:
                vals["Genero"] = employee.gender
                vals["Campo"] = employee.study_field
                vals["Study"] = employee.study_school
                vals["Nivel"] = employee.certificate
                if employee.resume_line_ids:
                    all_experiences = employee.resume_line_ids
                    experience_ids = User.get_experience(all_experiences, vals)
                    if experience_ids:
                        _logger.info('<<Experiencies recuperadas>>')
                if employee.employee_skill_ids:
                    all_skills = employee.employee_skill_ids
                    skill_ids = User.get_skills(all_skills, vals)
                    if skill_ids:
                        _logger.info('<<Habilidades recuperadas>>')
        return vals

    @classmethod
    def get_experience(self, all_experiences, vals):
        experiences = []
        for experience in all_experiences:
            val_exp = {
                "Sitio": experience.name,
                "Descripcion": experience.description,
            }
            experiences.append(val_exp)
        vals["Experiencia"] = experiences
        return vals

    @classmethod
    def get_skills(self, all_skills, vals):
        skills = []
        for skill in all_skills:
            val_skill = {
                "Skill": skill.skill_id.name,
                "Nivel": skill.skill_level_id.name,
            }
            skills.append(val_skill)
        vals["Habilidades"] = skills
        return vals

    # /hr_app/api/v1/user/register
    @http.route('/hr_app/api/' + version + '/user/register', auth="public", methods=['POST'], csrf=False, type='json', cors="*")
    def push_register(self, **kw):
        try:
            data_register = {
                'name': request.jsonrequest.get('name'),
                'login': request.jsonrequest.get('login'),
            }
            new_user = http.request.env['res.users'].sudo().create(data_register)
        except Exception as e:
            return {'status': 404, 'message': 'Register Error'}
        return {'status': 200, 'user_id': new_user.id, 'message': 'Registration request saved successfully'}

    @http.route('/' + version + '/', auth="public", methods=['GET'], csrf=False, type='json', cors="*")
    def hello(self):
        return {'status': 200, 'message': 'Hello API APP'}

