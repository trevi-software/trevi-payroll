# Copyright (C) 2026 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Tests for the Safaricom ET M-PESA API client and its callback controllers."""

from base64 import b64encode
from unittest.mock import MagicMock, PropertyMock, patch

from requests.exceptions import HTTPError

from odoo import tests

from odoo.addons.payroll_processor_mpesa_et.controllers.result import MyResultController
from odoo.addons.payroll_processor_mpesa_et.controllers.timeout import TimeoutController
from odoo.addons.payroll_processor_mpesa_et.models.payroll_processor_mpesa_et import (
    API_ENDPOINT_AUTH,
    API_ENDPOINT_PAYOUT,
    API_SERVER,
    MY_RESULT_ENDPOINT,
    MY_TIMEOUT_ENDPOINT,
)

REQUEST_PATH = (
    "odoo.addons.payroll_processor_mpesa_et.models.payroll_processor_mpesa_et.request"
)
BASE_URL = "https://payroll.example.com"


def fake_response(payload=None, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {} if payload is None else payload
    return response


def routes_of(func):
    """Return the paths a @route-decorated controller method answers."""
    routing = getattr(func, "original_routing", None) or {}
    return list(routing.get("routes", []))


class TestMpesaEtApiClient(tests.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Processor = cls.env["payroll.processor.mpesa_et"]
        cls.processor = cls.Processor.create(
            {
                "name": "Safaricom ET",
                "enabled": True,
                "consumer_key": "key",
                "consumer_secret": "secret",
                "party_a": "123456",
                "api_user": "user",
                "api_password": "pass",
            }
        )
        cls.env["ir.config_parameter"].sudo().set_param("web.base.url", BASE_URL)

    def test_authenticate_calls_the_token_endpoint(self):
        with patch(REQUEST_PATH) as request_mock:
            request_mock.return_value = fake_response(
                {"token_type": "Bearer", "access_token": "tok"}
            )
            result = self.processor.authenticate()

        self.assertEqual("Bearer", result["token_type"])
        args, kwargs = request_mock.call_args
        self.assertEqual("GET", args[0])
        self.assertEqual(
            f"https://{API_SERVER}{API_ENDPOINT_AUTH}?grant_type=client_credentials",
            args[1],
        )
        credentials = b64encode(b"key:secret").decode("utf-8")
        self.assertEqual({"Authorization": f"Basic {credentials}"}, kwargs["headers"])
        self.assertEqual(30, kwargs["timeout"])

    def test_authenticate_raises_for_an_http_error(self):
        with patch(REQUEST_PATH) as request_mock:
            response = fake_response(status_code=401)
            response.raise_for_status.side_effect = HTTPError("401 Client Error")
            request_mock.return_value = response
            with self.assertRaises(HTTPError):
                self.processor.authenticate()

    def test_get_authorization_joins_type_and_token(self):
        self.assertEqual(
            "Bearer tok",
            self.processor.get_authorization(
                {"token_type": "Bearer", "access_token": "tok"}
            ),
        )

    def test_payout_builds_the_request_the_api_expects(self):
        with patch(REQUEST_PATH) as request_mock:
            request_mock.return_value = fake_response({"ConversationId": "conv-1"})
            result = self.processor.payout(
                "Bearer tok", "+251911223344", 1234.5, "Payslip P1"
            )

        self.assertEqual("conv-1", result["ConversationId"])
        args, kwargs = request_mock.call_args
        self.assertEqual("POST", args[0])
        self.assertEqual(f"https://{API_SERVER}{API_ENDPOINT_PAYOUT}", args[1])
        self.assertEqual({"Authorization": "Bearer tok"}, kwargs["headers"])
        self.assertEqual(30, kwargs["timeout"])

        payload = kwargs["data"]
        self.assertEqual("user", payload["InitiatorName"])
        self.assertEqual("SalaryPayment", payload["CommandID"])
        self.assertEqual("123456", payload["PartyA"])
        self.assertEqual("+251911223344", payload["PartyB"])
        self.assertEqual(1234.5, payload["Amount"])
        self.assertEqual("Payslip P1", payload["Remarks"])
        self.assertEqual(
            f"{BASE_URL}/{MY_TIMEOUT_ENDPOINT}", payload["QueueTimeOutURL"]
        )
        self.assertEqual(f"{BASE_URL}/{MY_RESULT_ENDPOINT}", payload["ResultURL"])
        self.assertIsInstance(payload["SecurityCredential"], str)
        self.assertEqual(
            b64encode(b"pass").decode("utf-8"), payload["SecurityCredential"]
        )

    def test_payout_does_not_log_the_payment_password(self):
        """The payout credential is the base64-encoded password: never log it."""
        logger_name = (
            "odoo.addons.payroll_processor_mpesa_et.models.payroll_processor_mpesa_et"
        )
        with patch(REQUEST_PATH) as request_mock:
            request_mock.return_value = fake_response({"ConversationId": "conv-1"})
            with self.assertLogs(logger_name, level="INFO") as logs:
                self.processor.payout(
                    "Bearer tok", "+251911223344", 1234.5, "Payslip P1"
                )
        logged = "\n".join(logs.output)
        self.assertNotIn(
            b64encode(b"pass").decode("utf-8"), logged, "the password is not logged"
        )
        self.assertIn("SecurityCredential': '***'", logged)

    def test_payout_raises_for_an_http_error(self):
        with patch(REQUEST_PATH) as request_mock:
            response = fake_response(status_code=500)
            response.raise_for_status.side_effect = HTTPError("500 Server Error")
            request_mock.return_value = response
            with self.assertRaises(HTTPError):
                self.processor.payout("Bearer tok", "+251911223344", 1.0, "remarks")

    def test_translate_payment_response_maps_the_response(self):
        vals = self.processor.translate_payment_response(
            {
                "ConversationId": "conv-1",
                "OriginatorConversationID": "orig-1",
                "ResponseCode": "0",
                "ResponseDescription": "Accepted",
            }
        )
        self.assertEqual("conv-1", vals["ok_conversation"])
        self.assertEqual("orig-1", vals["ok_originator_conversation"])
        self.assertEqual("0", vals["ok_response_code"])
        self.assertEqual("Accepted", vals["ok_response_desc"])
        self.assertIsInstance(vals["raw"], str)
        self.assertIn("conv-1", vals["raw"])


class TestMpesaEtCallbacks(tests.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Result = cls.env["payslip.mpesa_et.result"]

    def test_callback_routes_match_the_urls_advertised_to_the_api(self):
        """The URLs handed to Safaricom must be the paths this module serves.

        ``payout()`` sends ``web.base.url`` + MY_RESULT_ENDPOINT /
        MY_TIMEOUT_ENDPOINT as ResultURL / QueueTimeOutURL, so those constants and
        the @route paths have to agree or the transaction result has nowhere to go.
        """
        self.assertIn(f"/{MY_RESULT_ENDPOINT}", routes_of(MyResultController.handler))
        self.assertIn(f"/{MY_TIMEOUT_ENDPOINT}", routes_of(TimeoutController.handler))

    def test_result_callback_records_the_transaction_result(self):
        params = {
            "result_type": 0,
            "result_code": 0,
            "result_desc": "The service request is processed successfully.",
            "originator_conversation": "orig-1",
            "conversation": "conv-1",
            "result_parameters": "[]",
            "tx_amount": 1234.5,
            "tx_receipt": "QK12ABC",
            "tx_completed_at": "2026-10-23 10:00:00",
            "recepient_public_name": "RICHARD",
            "recepient_is_registered_customer": True,
        }
        with patch.object(
            MyResultController, "env", new_callable=PropertyMock
        ) as env_mock:
            env_mock.return_value = self.env
            self.assertEqual({}, MyResultController().handler(**params))

        result = self.Result.search([("conversation", "=", "conv-1")], limit=1)
        self.assertTrue(result, "The transaction result was stored")
        self.assertTrue(result.result_ok)
        self.assertFalse(result.result_error)
        self.assertEqual(0, result.result_code)
        self.assertEqual("QK12ABC", result.tx_receipt)
        self.assertEqual(1234.5, result.tx_amount)
        self.assertEqual("RICHARD", result.recepient_public_name)
        self.assertIn("conv-1", result.raw)

    def test_timeout_callback_records_the_error(self):
        params = {
            "conversation": "conv-2",
            "originator_conversation": "orig-2",
            "result_code": 1037,
            "result_desc": "DS timeout user cannot be reached",
        }
        with patch.object(
            TimeoutController, "env", new_callable=PropertyMock
        ) as env_mock:
            env_mock.return_value = self.env
            TimeoutController().handler(**params)

        result = self.Result.search([("conversation", "=", "conv-2")], limit=1)
        self.assertTrue(result, "The timeout was stored")
        self.assertTrue(result.result_error)
        self.assertFalse(result.result_ok)
        self.assertEqual(1037, result.result_code)
        self.assertEqual("DS timeout user cannot be reached", result.result_desc)
