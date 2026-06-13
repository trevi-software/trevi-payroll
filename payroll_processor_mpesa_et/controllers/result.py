from odoo.http import Controller, Response, route

class ResultController(Controller):
    @route('/payroll_processor_mpesa_et/v1/result', type='json', auth='public', website=False, methods=['POST'], csrf=False)
    def handler(self):
        Response.render()
