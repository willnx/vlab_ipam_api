# -*- coding: UTF-8 -*-
"""
A suite of tests for the PortMapView object
"""
import unittest
from unittest.mock import patch, MagicMock

import ujson
from flask import Flask
from vlab_api_common import flask_common
from vlab_api_common.http_auth import generate_v2_test_token


from vlab_ipam_api.lib.views import portmap


class TestPortMapView(unittest.TestCase):
    """A set of test cases for the PortMapView object"""

    @classmethod
    def setUpClass(cls):
        """Runs once for the whole test suite"""
        cls.token = generate_v2_test_token(username='bob')
        portmap.const = MagicMock()
        portmap.const.VLAB_IPAM_OWNER = 'bob'
        portmap.const.VLAB_IPAM_LOG_LEVEL = 'INFO'
        portmap.const.VLAB_VERIFY_TOKEN = False

    @classmethod
    def setUp(cls):
        """Runs before every test case"""
        app = Flask(__name__)
        portmap.PortMapView.register(app)
        app.config['TESTING'] = True
        cls.app = app.test_client()
        # Mock FireWall
        cls.fake_firewall = MagicMock()
        app.firewall = cls.fake_firewall
        # Mock logger
        cls.fake_logger = MagicMock()
        portmap.logger = cls.fake_logger

    @patch.object(portmap, 'Database')
    def test_get(self, fake_Database):
        """GET on /api/1/ipam/portmap returns the port mapping rules"""
        fake_db = MagicMock()
        fake_db.lookup_port.return_value = {'worked': True}
        fake_Database.return_value.__enter__.return_value = fake_db
        resp = self.app.get('/api/1/ipam/portmap',
                            headers={'X-Auth': self.token})

        output = resp.json['content']
        expected = {'worked': True}

        self.assertEqual(output, expected)

    @patch.object(portmap, 'Database')
    def test_get_bad_conn_port(self, fake_Database):
        """GET on /api/1/ipam/portmap returns HTTP 400 is supplied with a bad value for conn_port"""
        fake_db = MagicMock()
        fake_db.lookup_port.return_value = {'worked': True}
        fake_Database.return_value.__enter__.return_value = fake_db
        resp = self.app.get('/api/1/ipam/portmap?conn_port=asdf',
                            headers={'X-Auth': self.token})

        expected = 400

        self.assertEqual(resp.status_code, expected)

    @patch.object(portmap, 'Database')
    def test_get_bad_target_port(self, fake_Database):
        """GET on /api/1/ipam/portmap returns HTTP 400 is supplied with a bad value for target_port"""
        fake_db = MagicMock()
        fake_db.lookup_port.return_value = {'worked': True}
        fake_Database.return_value.__enter__.return_value = fake_db
        resp = self.app.get('/api/1/ipam/portmap?target_port=asdf',
                            headers={'X-Auth': self.token})

        expected = 400

        self.assertEqual(resp.status_code, expected)
    @patch.object(portmap, 'Database')
    def test_get_doh_status(self, fake_Database):
        """GET on /api/1/ipam/portmap returns HTTP 500 upon error"""
        fake_Database.return_value.__enter__.side_effect = [RuntimeError('testing')]
        resp = self.app.get('/api/1/ipam/portmap',
                            headers={'X-Auth': self.token})

        expected = 500

        self.assertEqual(resp.status_code, expected)

    @patch.object(portmap, 'Database')
    def test_get_doh_msg(self, fake_Database):
        """GET on /api/1/ipam/portmap sets the error in the response upon failure"""
        fake_Database.return_value.__enter__.side_effect = [RuntimeError('testing')]
        resp = self.app.get('/api/1/ipam/portmap',
                            headers={'X-Auth': self.token})

        msg = resp.json['error']
        expected = 'testing'

        self.assertEqual(msg, expected)

    @patch.object(portmap, 'Database')
    def test_port(self, fake_Database):
        """POST on /api/1/ipam/portmap returns 200 upon success"""
        resp = self.app.post('/api/1/ipam/portmap',
                             headers={'X-Auth': self.token},
                             json={'target_addr': '1.1.1.1',
                                   'target_port': 5698,
                                   'target_name': "myBox",
                                   'target_component': "OneFS"})

        self.assertEqual(resp.status_code, 200)

    @patch.object(portmap, 'Database')
    def test_port_db_error(self, fake_Database):
        """POST on /api/1/ipam/portmap returns 500 if the database generates an error"""
        fake_Database.side_effect = [portmap.DatabaseError('testing', pgcode='234')]

        resp = self.app.post('/api/1/ipam/portmap',
                             headers={'X-Auth': self.token},
                             json={'target_addr': '1.1.1.1',
                                   'target_port': 5698,
                                   'target_name': "myBox",
                                   'target_component': "OneFS"})

        self.assertEqual(resp.status_code, 500)

    @patch.object(portmap, 'Database')
    def test_port_firewall_error(self, fake_Database):
        """POST on /api/1/ipam/portmap returns 500 if unable to add firewall rule"""
        self.fake_firewall.map_port.side_effect = [OSError('testing')]
        resp = self.app.post('/api/1/ipam/portmap',
                             headers={'X-Auth': self.token},
                             json={'target_addr': '1.1.1.1',
                                   'target_port': 5698,
                                   'target_name': "myBox",
                                   'target_component': "OneFS"})

        self.assertEqual(resp.status_code, 500)

    @patch.object(portmap, 'remove_port_map')
    @patch.object(portmap, 'records_valid')
    @patch.object(portmap, 'Database')
    def test_delete_ok(self, fake_Database, fake_records_valid, fake_remove_port_map):
        """DELETE on /api/1/ipam/portmap returns HTTP 200 upon success"""
        fake_db = MagicMock()
        fake_db.port_info.return_value = (22, '1.2.3.4')
        fake_Database.return_value.__enter__.return_value = fake_db
        fake_records_valid.return_value = ('', 200)
        fake_remove_port_map.return_value = (None, 200)
        resp = self.app.delete('/api/1/ipam/portmap',
                               headers={'X-Auth': self.token},
                               json={'conn_port': 5698})

        self.assertEqual(resp.status_code, 200)

    @patch.object(portmap, 'remove_port_map')
    @patch.object(portmap, 'records_valid')
    @patch.object(portmap, 'Database')
    def test_delete_db_error(self, fake_Database, fake_records_valid, fake_remove_port_map):
        """DELETE on /api/1/ipam/portmap returns HTTP 500 when there is a database error"""
        fake_Database.return_value.__enter__.side_effect = [RuntimeError('testing')]
        fake_records_valid.return_value = ('', 200)
        fake_remove_port_map.return_value = (None, 200)

        resp = self.app.delete('/api/1/ipam/portmap',
                               headers={'X-Auth': self.token},
                               json={'conn_port': 5698})

        self.assertEqual(resp.status_code, 500)


class TestPortMapRecordsValid(unittest.TestCase):
    """A suite of test cases for the ``records_valid`` function"""

    def test_records_valid(self):
        """``records_valid`` returns a tuple of ('', 200) when supplied records are OK"""
        output = portmap.records_valid(nat_id='3',
                                       filter_id='5',
                                       target_port='22',
                                       target_addr='2.3.4.5')
        expected = ("", 200)

        self.assertEqual(output, expected)

    def test_records_valid_no_record(self):
        """``records_valid`` an error message and HTTP 404 when no record exists"""
        output = portmap.records_valid(nat_id=None,
                                       filter_id=None,
                                       target_port=None,
                                       target_addr=None)
        expected = ("No such port mapping record", 404)

        self.assertEqual(output, expected)

    def test_records_valid_no_iptables(self):
        """``records_valid`` generates useful error and status code when record only exists in iptables"""
        output = portmap.records_valid(nat_id=None,
                                       filter_id=None,
                                       target_port='22',
                                       target_addr='2.3.4.5')

        error = "DB record exist, but no iptable record; contact admin."
        status = 500

        self.assertEqual(output, (error, status))

    def test_records_valid_no_db(self):
        """``records_valid`` generates useful error and status code when record only exists in database"""
        output = portmap.records_valid(nat_id='23',
                                       filter_id='43',
                                       target_port=None,
                                       target_addr=None)

        error = "iptable record exist, but no DB record; contact admin."
        status = 500

        self.assertEqual(output, (error, status))


class TestRemovePortMap(unittest.TestCase):
    """A suite of test cases for the ``remove_port_map`` function"""

    @classmethod
    def setUpClass(cls):
        """Runs once for the whole test suite"""
        cls.token = generate_v2_test_token(username='bob')
        portmap.const = MagicMock()
        portmap.const.VLAB_IPAM_OWNER = 'bob'
        portmap.const.VLAB_IPAM_LOG_LEVEL = 'INFO'
        portmap.const.VLAB_VERIFY_TOKEN = False

    @classmethod
    def setUp(cls):
        """Runs before every test case"""
        cls.full_app = app = Flask(__name__)
        portmap.PortMapView.register(cls.full_app)
        cls.full_app.config['TESTING'] = True
        cls.app = app.test_client()
        # Mock FireWall
        cls.fake_firewall = MagicMock()
        app.firewall = cls.fake_firewall
        # Mock logger
        cls.fake_logger = MagicMock()
        portmap.logger = cls.fake_logger

    def test_remove_port_map(self):
        """``remove_port_map`` returns no error and HTTP 200 upon success"""
        fake_db = MagicMock()
        with self.full_app.app_context():
            output = portmap.remove_port_map(nat_id='2',
                                             filter_id='3',
                                             target_port='22',
                                             target_addr='2.3.4.5',
                                             conn_port=2345,
                                             db=fake_db)

        expected = (None, 200)

        self.assertEqual(output, expected)

    def test_remove_port_map_delete_2_fails(self):
        """``remove_port_map`` returns an error and HTTP 500 if unable to delete the 2nd iptables rule"""
        fake_db = MagicMock()
        self.fake_firewall.delete_rule.side_effect = [None, RuntimeError('testing')]
        with self.full_app.app_context():
            output = portmap.remove_port_map(nat_id='2',
                                             filter_id='3',
                                             target_port='22',
                                             target_addr='2.3.4.5',
                                             conn_port=2345,
                                             db=fake_db)

        expected = ('testing', 500)

        self.assertEqual(output, expected)

    def test_remove_port_map_delete_2_undo(self):
        """``remove_port_map`` remakes the 1st rule if deleting the 2nd rule fails"""
        fake_db = MagicMock()
        self.fake_firewall.delete_rule.side_effect = [None, RuntimeError('testing')]
        with self.full_app.app_context():
            output = portmap.remove_port_map(nat_id='2',
                                             filter_id='3',
                                             target_port='22',
                                             target_addr='2.3.4.5',
                                             conn_port=2345,
                                             db=fake_db)

        self.assertEqual(self.fake_firewall.forward.call_count, 1)

    def test_remove_port_map_db_fail(self):
        """``remove_port_map`` returns an error and HTTP 500 if unable delete the DB record"""
        fake_db = MagicMock()
        fake_db.delete_port.side_effect = [RuntimeError('testing')]
        with self.full_app.app_context():
            output = portmap.remove_port_map(nat_id='2',
                                             filter_id='3',
                                             target_port='22',
                                             target_addr='2.3.4.5',
                                             conn_port=2345,
                                             db=fake_db)

        expected = ('testing', 500)

        self.assertEqual(output, expected)

    def test_remove_port_map_db_undo(self):
        """``remove_port_map`` remakes both iptable rules if unable to delete record from database"""
        fake_db = MagicMock()
        fake_db.delete_port.side_effect = [RuntimeError('testing')]
        with self.full_app.app_context():
            output = portmap.remove_port_map(nat_id='2',
                                             filter_id='3',
                                             target_port='22',
                                             target_addr='2.3.4.5',
                                             conn_port=2345,
                                             db=fake_db)
        self.assertEqual(self.fake_firewall.map_port.call_count, 1)


if __name__ == '__main__':
    unittest.main()
