# -*- coding: UTF-8 -*-
"""
A suite of tests for the healthcheck API end point
"""
import unittest
from unittest.mock import patch

from flask import Flask

from vlab_ipam_api.lib.views import healthcheck


class TestHealthView(unittest.TestCase):
    """A set of test cases for the HealthView object"""

    @classmethod
    def setUp(cls):
        """Runs before every test case"""
        app = Flask(__name__)
        healthcheck.HealthView.register(app)
        app.config['TESTING'] = True
        cls.app = app.test_client()

    @patch.object(healthcheck.firewall, 'run_cmd')
    @patch.object(healthcheck, 'Database')
    def test_health_check_ok(self, fake_Database, fake_run_cmd):
        """Healthcheck returns HTTP 200 when everything is OK"""
        resp = self.app.get('/api/1/ipam/healthcheck')

        expected = 200

        self.assertEqual(expected, resp.status_code)

    @patch.object(healthcheck.firewall, 'run_cmd')
    @patch.object(healthcheck, 'Database')
    def test_health_check_keys(self, fake_Database, fake_run_cmd):
        """Healthcheck returns expected info in JSON response"""
        resp = self.app.get('/api/1/ipam/healthcheck')

        expected = ['version', 'firewall', 'database']
        actual = resp.json.keys()
        # set() avoids false positives due to order
        self.assertEqual(set(expected), set(actual))

    @patch.object(healthcheck.firewall, 'run_cmd')
    @patch.object(healthcheck, 'Database')
    def test_health_check_db_error(self, fake_Database, fake_run_cmd):
        """The healthcheck returns HTTP 500 when the database generates an error"""
        fake_Database.side_effect = [Exception('testing')]
        resp = self.app.get('/api/1/ipam/healthcheck')

        expected = 500

        self.assertEqual(expected, resp.status_code)


if __name__ == '__main__':
    unittest.main()
