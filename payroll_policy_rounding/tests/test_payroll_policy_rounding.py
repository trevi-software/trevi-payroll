# Copyright (C) 2022 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import fields
from odoo.tools import mute_logger

from . import common


class TestPolicy(common.TestPolicyCommon):
    def test_get_latest_policy(self):
        pMarch = self.Policy.create(
            {"name": "P1", "date": date(2020, 3, 1), "tz": "UTC"}
        )
        pDec = self.Policy.create(
            {"name": "P1", "date": date(2020, 12, 1), "tz": "UTC"}
        )
        pJan = self.Policy.create({"name": "P1", "date": date(2020, 1, 1), "tz": "UTC"})
        pg = self.PolicyGroup.create(
            {
                "name": "PGroup",
                "rounding_policy_ids": [(6, 0, [pDec.id, pMarch.id, pJan.id])],
            }
        )
        ap = self.Policy.get_latest_policy(pg, date.today())

        self.assertEqual(ap, pDec, "I got the latest policy from available ones")

    def test_get_latest_policy_with_future(self):
        pastDate = date.today() - relativedelta(days=5)
        futureDate = date.today() + relativedelta(days=1)
        pFuture = self.Policy.create({"name": "PF", "date": futureDate, "tz": "UTC"})
        pPast = self.Policy.create({"name": "PP", "date": pastDate, "tz": "UTC"})
        pg = self.PolicyGroup.create(
            {
                "name": "PGroup",
                "rounding_policy_ids": [(6, 0, [pFuture.id, pPast.id])],
            }
        )
        ap = self.Policy.get_latest_policy(pg, date.today())

        self.assertEqual(ap, pPast, "The lastest policy is not in the future")

    def test_duplicate_attendance_type_rejected(self):
        """A policy cannot hold two lines with the same attendance type."""

        p = self.Policy.create({"name": "PDUP", "date": date.today(), "tz": "UTC"})
        self.PolicyLine.create(
            {
                "policy_id": p.id,
                "attendance_type": "in",
                "round_type": "down",
                "round_interval": 5,
            }
        )
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.PolicyLine.create(
                {
                    "policy_id": p.id,
                    "attendance_type": "in",
                    "round_type": "up",
                    "round_interval": 5,
                }
            )

    def test_late_out_rounds_from_scheduled_end(self):
        """A late check-out rounds from the scheduled end, not the start.

        For an 08:00-17:10 shift and 15 minute rounding up, a 17:11 punch must
        become 17:25 (17:10 + 15), not 17:15 (08:00 + 9h15).
        """

        line = self.PolicyLine.create(
            {
                "attendance_type": "out",
                "round_type": "up",
                "round_interval": 15,
            }
        )
        utcdt_in = datetime(2024, 1, 1, 8, 0)
        utcdt_out = datetime(2024, 1, 1, 17, 10)
        punch = datetime(2024, 1, 1, 17, 11)

        res = line.calculate_rounding_clock_out(punch, (utcdt_in, utcdt_out, None))

        self.assertEqual(
            res,
            fields.Datetime.to_string(datetime(2024, 1, 1, 17, 25)),
            "The late check-out is rounded from the scheduled end time",
        )

    def test_early_out_rounds_with_preauth_ot(self):
        """An early check-out is still rounded down when preauth OT is on.

        A 16:59 punch for a 17:00 finish with a 15 minute interval and
        ``round_type`` 'down' must become 16:45, even with pre-authorized OT
        enabled (the preauth check only caps overtime *after* the shift end).
        """

        line = self.PolicyLine.create(
            {
                "attendance_type": "out",
                "round_type": "down",
                "round_interval": 15,
                "preauth_ot": True,
            }
        )
        utcdt_in = datetime(2024, 1, 1, 8, 0)
        utcdt_out = datetime(2024, 1, 1, 17, 0)
        punch = datetime(2024, 1, 1, 16, 59)

        res = line.calculate_rounding_clock_out(punch, (utcdt_in, utcdt_out, None))

        self.assertEqual(
            res,
            fields.Datetime.to_string(datetime(2024, 1, 1, 16, 45)),
            "The early check-out is rounded down despite pre-authorized OT",
        )
