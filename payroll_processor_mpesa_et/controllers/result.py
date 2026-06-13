from odoo.http import Controller, Response, route

class ResultController(Controller):
    @route('/payroll_processor_mpesa_et/v1/result', type='json', auth='public', website=False, methods=['POST'], csrf=False)
    def handler(self, **kwargs):
        type = kwargs.get('result_type')
        code = kwargs.get('result_code')
        desc = kwargs.get('result_desc')
        originator_conversation = kwargs.get('originator_conversation')
        conversation = kwargs.get('conversation')
        result_parameters = kwargs.get('result_parameters')
        tx_amount = kwargs.get('tx_amount')
        tx_receipt = kwargs.get('tx_receipt')
        tx_completed_at = kwargs.get('tx_completed_at')
        recepient_public_name = kwargs.get('recepient_public_name')
        recepient_is_registered_customer = kwargs.get('recepient_is_registered_customer')

        self.env["payslip.mpesa_et.result"].create({
            "result_type": type,
            "result_code": code,
            "result_desc": desc,
            "originator_conversation": originator_conversation,
            "conversation": conversation,
            "result_parameters": result_parameters,
            "tx_amount": tx_amount,
            "tx_receipt": tx_receipt,
            "tx_completed_at": tx_completed_at,
            "recepient_public_name": recepient_public_name,
            "recepient_is_registered_customer": recepient_is_registered_customer,
            "raw": str(kwargs)
        })
