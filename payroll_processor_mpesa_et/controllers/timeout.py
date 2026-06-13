from odoo.http import Controller, Response, route

class TimeoutController(Controller):
    @route('/payroll_processor_mpesa_et/v1/timeout', type='json', auth='public', website=False, methods=['POST'], csrf=False)
    def handler(self, **kwargs):
        conversation = kwargs.get('conversation')
        originator_conversation = kwargs.get('originator_conversation')
        result_code = kwargs.get('result_code')
        result_desc = kwargs.get('result_desc')

        self.env["payslip.mpesa_et.result"].create({
            "conversation": conversation,
            "originator_conversation": originator_conversation,
            "result_code": result_code,
            "result_desc": result_desc,
            "raw": str(kwargs)
        })
