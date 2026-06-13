from base64 import b64encode
from json import loads
from requests import codes, request
from typing import Dict
import logging

from odoo import fields, models

API_SERVER = "apisandbox.safaricom.et"
API_ENDPOINT_AUTH = "/v1/token/generate"
API_ENDPOINT_PAYOUT = "/mpesa/b2c/v2/paymentrequest"
MY_TIMEOUT_ENDPOINT = "payroll_processor_mpesa_et/timeout"
MY_RESULT_ENDPOINT = "payroll_processor_mpesa_et/result"

IS_ENABLED = "enabled == true"

_logger = logging.getLogger(__name__)


class PayrollProcessorMpesaEt(models.Model):

    _name = "payroll.processor.mpesa_et"
    _description = "Safaricom Ethiopia M-PESA Payroll Integration"

    enabled = fields.Boolean(
        copy=False,
        help="""* If the processor should process payslips the status should be \'Enabled\'.
        \n* If the processor should NOT process payslips the status should be \'Disabled\'.""",
    )
    
    name = fields.Char(readonly=IS_ENABLED)

    consumer_key = fields.Char(string="API Key", readonly=IS_ENABLED, copy=False)

    consumer_secret = fields.Char(string="API Secret", readonly=IS_ENABLED, copy=False)
 
    party_a = fields.Char(name="Business Shortcode", readonly=IS_ENABLED)

    api_user = fields.Char(string="User Name", readonly=IS_ENABLED)

    api_password = fields.Char(string="Password", readonly=IS_ENABLED, copy=False)

    def authenticate(self) -> Dict[str, str]:
        """
        Authenticate against the Safaricom ET API.

        Args:
            None

        Returns:
            Dict[str, str]: The response from the authentication endpoint.
        """


        api_server = API_SERVER
        api_endpoint = API_ENDPOINT_AUTH
        api_auth_query = "grant_type=client_credentials"
        endpoint = "".join("https://").join(api_server).join(api_endpoint).join("?").join(api_auth_query)
        authorization = "".join("Basic ", b64encode("".join(self.consumer_key, ":", self.consumer_secret).encode('utf-8')))
        headers = {'Authorization': authorization}
        response = request("GET", endpoint, headers=headers)

        if response.status_code == codes.ok:
            return loads(response.json())
        else:
            response.raise_for_status()
    
    def get_authorization(self, auth_response: Dict[str, str]) -> str:
        """
        Get a bearer authorization from a successful authentication response
        from the Safaricom ET API.

        Args:
            auth_response (Dict[str, str]): The authentication response data.

        Returns:
            str: The bearer authorization token.
        """

        bearer_auth = "".join(auth_response["token_type"]).join(" ").join(auth_response["access_token"])
        
        return bearer_auth
    
    def payout(self, bearer_auth: str, party_b: str, amount: float, remarks: str) -> Dict[str, str]:
        """
        Initiate a B2C payment request on the Safaricom ET API.

        Args:
            bearer_auth (str): The bearer authorization token.
            party_b (str): The recipient's phone number.
            amount (float): The amount to be paid.
            remarks (str): Remarks for the transaction.
        
        Returns:
            Dict[str, str]: API response data.

        Raises:
            HTTPError: For HTTP-related errors.
        """

        api_server = API_SERVER
        api_endpoint = API_ENDPOINT_PAYOUT
        endpoint = "".join("https://").join(api_server).join(api_endpoint)
        timeout_url = "".join(self.env['ir.config_parameter'].sudo().get_param('web.base.url')).join("/").join(MY_TIMEOUT_ENDPOINT)
        result_url = "".join(self.env['ir.config_parameter'].sudo().get_param('web.base.url')).join("/").join(MY_RESULT_ENDPOINT)
        command = "SalaryPayment"
        occasion = "Disbursement"
        headers = {"Authorization": bearer_auth}
        payload = {
            "InitiatorName": self.api_user,
            "SecurityCredential": b64encode(self.api_password.encode('utf-8')),
            "Occassion": occasion,
            "CommandID": command,
            "PartyA": self.party_a,
            "PartyB": party_b,
            "Remarks": remarks,
            "Amount": amount,
            "QueueTimeOutURL": timeout_url,
            "ResultURL": result_url
        }

        _logger.info(
            "Initiating M-PESA payment request to %s for amount %s to endpoint: %s"
            " with payload: %s", party_b, amount, endpoint, payload
        )
        response = request("POST", endpoint, headers=headers, data=payload)

        if response.status_code == codes.ok:
            _logger.info(
                "Payment request successful. Response: {response.text}"
            )
            return loads(response.json())
        else:
            response.raise_for_status()

    def translate_payment_response(self, response: Dict[str, str]) -> Dict[str, str]:

       return {
           "ok_conversation": response["ConversationId"],
           "ok_originator_conversation": response["OriginatorConversationID"],
           "ok_response_code": response["ResponseCode"],
           "ok_response_desc": response["ResponseDescription"],
           "raw": response.__str__
       }
