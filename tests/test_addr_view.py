"""
A suite of tests for the AddrView object
"""
import unittest
from unittest.mock import patch, MagicMock

import ujson
from flask import Flask
from vlab_api_common import flask_common
from vlab_api_common.http_auth import generate_v2_test_token


from vlab_ipam_api.lib.views import addr


class TestAddrView(unittest.TestCase):
    """A set of test cases for the AddrView object"""

    @classmethod
    def setUpClass(cls):
        """Runs once for the whole test suite"""
        cls.token = generate_v2_test_token(username='bob')
        addr.const = MagicMock()
        addr.const.VLAB_IPAM_LOG_LEVEL = 'INFO'
        addr.const.VLAB_VERIFY_TOKEN = False

    @classmethod
    def setUp(cls):
        """Runs before every test case"""
        app = Flask(__name__)
        addr.AddrView.register(app)
        app.config['TESTING'] = True
        cls.app = app.test_client()
        # Mock logger
        cls.fake_logger = MagicMock()
        addr.logger = cls.fake_logger

    @patch.object(addr, 'Database')
    def test_get(self, fake_Database):
        """GET on /api/1/ipam/addr returns 200 OK upon success"""
        resp = self.app.get('/api/1/ipam/addr',
                            headers={'X-Auth': self.token})

        expected = 200

        self.assertEqual(resp.status_code, expected)

    @patch.object(addr, 'args_valid')
    def test_get_bad_args(self, fake_args_valid):
        """GET on /api/1/ipam/addr returns 400 if supplied with bad query parameters"""
        fake_args_valid.return_value = False
        resp = self.app.get('/api/1/ipam/addr',
                            headers={'X-Auth': self.token})

        expected = 400

        self.assertEqual(resp.status_code, expected)

    def test_args_valid_none(self):
        """``args_valid`` a value of None for all args is OK"""
        output = addr.args_valid(name=None, addr=None, component=None)

        self.assertTrue(output)

    def test_args_valid_name(self):
        """``args_valid`` returns True if supplied with just the "name" param"""
        output = addr.args_valid(name='someBox', addr=None, component=None)

        self.assertTrue(output)

    def test_args_valid_addr(self):
        """``args_valid`` returns True if supplied with just a valid IPv4 param"""
        output = addr.args_valid(name=None, addr='1.2.3.4', component=None)

        self.assertTrue(output)

    def test_args_valid_component(self):
        """``args_valid`` returns True if supplied with just the "component" param"""
        output = addr.args_valid(name=None, addr='', component='someComponent')

        self.assertTrue(output)

    def test_args_valid_name_and_addr(self):
        """``args_valid`` returns False if supplied with both name and addr param"""
        output = addr.args_valid(name='myBox', addr='1.2.3.4', component=None)

        self.assertFalse(output)

    def test_args_valid_name_and_component(self):
        """``args_valid`` returns False if supplied with both name and component param"""
        output = addr.args_valid(name='myBox', addr='', component='someComponent')

        self.assertFalse(output)

    def test_args_valid_component_and_addr(self):
        """``args_valid`` returns False if supplied with both component and addr param"""
        output = addr.args_valid(name=None, addr='1.2.3.4', component='someComponent')

        self.assertFalse(output)

    def test_args_valid_all_params(self):
        """``args_valid`` returns False if supplied with all params"""
        output = addr.args_valid(name='myBox', addr='1.2.3.4', component='someComponent')

        self.assertFalse(output)

    def test_args_valid_bad_ip(self):
        """``args_valid`` returns False if supplied with an invalid IPv4 address"""
        output = addr.args_valid(name=None, addr='900.2.3.4', component=None)

        self.assertFalse(output)


if __name__ == '__main__':
    unittest.main()
