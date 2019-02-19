# -*- coding: UTF-8 -*-
"""
Unit tests for the vlab_ipam_api.lib.database module
"""
import types
import unittest
from mock import MagicMock, patch

import psycopg2

from vlab_ipam_api.lib import database


class TestDatabase(unittest.TestCase):
    """A suite of tests for the vlab_ipam_api.lib.database module"""

    def setUp(self):
        """Runs before every test case"""
        # mock away the psycopg2 module
        self.patcher = patch('vlab_ipam_api.lib.database.psycopg2.connect')
        self.mocked_connection = MagicMock()
        self.mocked_cursor = MagicMock()
        self.mocked_connection.cursor.return_value = self.mocked_cursor
        self.mocked_conn = self.patcher.start()
        self.mocked_conn.return_value = self.mocked_connection

    def tearDown(self):
        """Runs after every test case"""
        self.patcher.stop()

    def test_init(self):
        """Simple test that we can instantiate Database class for testing"""
        db = database.Database()
        self.assertTrue(isinstance(db, database.Database))
        self.assertTrue(db._connection is self.mocked_connection)
        self.assertTrue(db._cursor is self.mocked_cursor)

    def test_context_manager(self):
        """Database support use of `with` statement and auto-closes connection"""
        with database.Database() as db:
            pass
        self.assertTrue(self.mocked_connection.close.call_count is 1)

    def test_close(self):
        """Calling Database.close() closes the connection to the DB"""
        db = database.Database()
        db.close()
        self.assertTrue(self.mocked_connection.close.call_count is 1)

    def test_execute(self):
        """Happy path test for the Database.execute method"""
        self.mocked_cursor.fetchall.return_value = []

        db = database.Database()
        result = db.execute(sql="SELECT * from FOO WHERE bar LIKE 'baz'")
        self.assertTrue(isinstance(result, list))

    def test_database_error(self):
        """``execute`` database.DatabaseError instead of psycopg2 errors"""
        self.mocked_cursor.execute.side_effect = psycopg2.Error('testing')

        db = database.Database()

        with self.assertRaises(database.DatabaseError):
            db.execute(sql="SELECT * from FOO WHERE bar LIKE 'baz'")

    def test_auto_rollback(self):
        """``execute`` auto rollsback the db connection upon error"""
        self.mocked_cursor.execute.side_effect = psycopg2.Error('testing')

        db = database.Database()
        try:
            db.execute(sql="SELECT * from FOO WHERE bar LIKE 'baz'")
        except database.DatabaseError:
            pass

        self.assertEqual(self.mocked_connection.rollback.call_count, 1)

    def test_no_results(self):
        """``execute`` returns an empty list when no query has no results"""
        self.mocked_cursor.description = None

        db = database.Database()
        result = db.execute(sql="SELECT * from FOO WHERE bar LIKE 'baz'")
        self.assertTrue(isinstance(result, list))

    def test_add_port(self):
        """``add_port`` returns the port number upon success"""
        db = database.Database()
        port = db.add_port(target_addr='1.1.1.1',
                           target_port=22,
                           target_name='myBox',
                           target_component='OneFS')
        self.assertTrue(isinstance(port, int))

    def test_add_port_db_error(self):
        """``add_port`` raises DatabaseError for unexpected DB problems"""
        self.mocked_cursor.execute.side_effect = psycopg2.Error('testing')

        db = database.Database()

        with self.assertRaises(database.DatabaseError):
            db.add_port(target_addr='1.1.1.1',
                        target_port=22,
                        target_name='myBox',
                        target_component='OneFS')

    def test_port_taken(self):
        """``add_port`` retries with a new random port number if the DB already
        has a record for the requested conn_port"""
        self.mocked_cursor.execute.side_effect = [database.DatabaseError('testing', pgcode='23505'), None]

        db = database.Database()
        port = db.add_port(target_addr='1.1.1.1',
                           target_port=22,
                           target_name='myBox',
                           target_component='OneFS')

        self.assertEqual(self.mocked_cursor.execute.call_count, 2)

    def test_port_taken_runtime_Error(self):
        """``add_port`` raises RuntimeError if unable to add port to DB"""
        self.mocked_cursor.execute.side_effect = database.DatabaseError('testing', pgcode='23505')

        db = database.Database()
        with self.assertRaises(RuntimeError):
            db.add_port(target_addr='1.1.1.1',
                        target_port=22,
                        target_name='myBox',
                        target_component='OneFS')

    def test_delete_port(self):
        """``delete_port`` executes the expected SQL to delete the record"""
        db = database.Database()
        db.delete_port(conn_port=9001)

        args, _ = self.mocked_cursor.execute.call_args
        sent_sql = args[0]
        expected_sql = "DELETE FROM ipam WHERE conn_port=(%s);"

        self.assertEqual(sent_sql, expected_sql)

    def test_port_info(self):
        """``port_info`` returns the target port and target ip when the record exists"""
        self.mocked_cursor.fetchall.return_value = [(22, '1.2.3.4')]

        db = database.Database()
        result = db.port_info(conn_port=9001)
        expected = (22, '1.2.3.4')

        self.assertEqual(result, expected)

    def test_port_info_none(self):
        """``port_info`` returns (None, None) if the record does not exist"""
        self.mocked_cursor.description = None

        db = database.Database()
        result = db.port_info(conn_port=9001)
        expected = (None, None)

        self.assertEqual(result, expected)

    def test_lookup_addr_name(self):
        """``lookup_addr`` returns a dictionary when query via name param"""
        self.mocked_cursor.fetchall.return_value = [('myTarget', '1.2.3.4', 'someComponent', True)]

        db = database.Database()
        result = db.lookup_addr(name='myTarget', addr=None, component=None)
        expected = {'myTarget': {'addr': ['1.2.3.4'], 'component' : 'someComponent', 'routable': True}}

        self.assertEqual(result, expected)

    def test_lookup_addr_addr(self):
        """``lookup_addr`` returns a dictionary when query via addr param"""
        self.mocked_cursor.fetchall.return_value = [('myTarget', '1.2.3.4', 'someComponent', True)]

        db = database.Database()
        result = db.lookup_addr(name=None, addr='1.2.3.4', component=None)
        expected = {'myTarget': {'addr': ['1.2.3.4'], 'component' : 'someComponent', 'routable': True}}

        self.assertEqual(result, expected)

    def test_lookup_addr_component(self):
        """``lookup_addr`` returns a dictionary when query via component param"""
        self.mocked_cursor.fetchall.return_value = [('myTarget', '1.2.3.4', 'someComponent', True)]

        db = database.Database()
        result = db.lookup_addr(name=None, addr=None, component='someComponent')
        expected = {'myTarget': {'addr': ['1.2.3.4'], 'component' : 'someComponent', 'routable': True}}

        self.assertEqual(result, expected)

    def test_lookup_addr_multiple_ips(self):
        """``lookup_addr`` returns all IPs"""
        self.mocked_cursor.fetchall.return_value = [('myTarget', '1.2.3.4', 'someComponent', True),
                                                    ('myTarget', '2.3.4.5', 'someComponent', True)]

        db = database.Database()
        result = db.lookup_addr(name=None, addr=None, component='someComponent')
        expected = {'myTarget': {'addr': ['1.2.3.4', '2.3.4.5'], 'component' : 'someComponent', 'routable': True}}

        self.assertEqual(result, expected)

    def test_lookup_addr_none(self):
        """``lookup_addr`` returns a dictionary when all params are none"""
        self.mocked_cursor.fetchall.return_value = [('myTarget', '1.2.3.4', 'someComponent', True)]

        db = database.Database()
        result = db.lookup_addr(name=None, addr=None, component=None)
        expected = {'myTarget': {'addr': ['1.2.3.4'], 'component' : 'someComponent', 'routable': True}}

        self.assertEqual(result, expected)

    def test_lookup_port(self):
        """``lookup_port`` generates correct SQL when no clauses are supplied"""
        db = database.Database()
        db.lookup_port()

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, _ = call_args
        expected = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam;'

        self.assertEqual(sql, expected)

    def test_lookup_port_by_name(self):
        """``lookup_port`` generates correct SQL when the "name" clause is supplied"""
        db = database.Database()
        db.lookup_port(name='foo')

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, call_params = call_args
        expected_sql = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam WHERE target_name LIKE (%s);'
        expected_params = ('foo',)

        self.assertEqual(sql, expected_sql)
        self.assertEqual(call_params, expected_params)

    def test_lookup_port_by_addr(self):
        """``lookup_port`` generates correct SQL when the "addr" clause is supplied"""
        db = database.Database()
        db.lookup_port(addr='192.168.1.2')

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, call_params = call_args
        expected_sql = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam WHERE target_addr LIKE (%s);'
        expected_params = ('192.168.1.2',)

        self.assertEqual(sql, expected_sql)
        self.assertEqual(call_params, expected_params)

    def test_lookup_port_by_component(self):
        """``lookup_port`` generates correct SQL when the "component" clause is supplied"""
        db = database.Database()
        db.lookup_port(component='OneFS')

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, call_params = call_args
        expected_sql = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam WHERE target_component LIKE (%s);'
        expected_params = ('OneFS',)

        self.assertEqual(sql, expected_sql)
        self.assertEqual(call_params, expected_params)

    def test_lookup_port_by_conn_port(self):
        """``lookup_port`` generates correct SQL when the "conn_port" clause is supplied"""
        db = database.Database()
        db.lookup_port(conn_port=9001)

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, call_params = call_args
        expected_sql = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam WHERE conn_port = (%s);'
        expected_params = (9001,)

        self.assertEqual(sql, expected_sql)
        self.assertEqual(call_params, expected_params)

    def test_lookup_port_by_target_port(self):
        """``lookup_port`` generates correct SQL when the "target_port" clause is supplied"""
        db = database.Database()
        db.lookup_port(target_port=22)

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, call_params = call_args
        expected_sql = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam WHERE target_port = (%s);'
        expected_params = (22,)

        self.assertEqual(sql, expected_sql)
        self.assertEqual(call_params, expected_params)

    def test_lookup_port_by_all(self):
        """``lookup_port`` generates correct SQL when the all clauses are supplied"""
        db = database.Database()
        db.lookup_port(name='myVM', addr='1.2.3.4', component='CEE', conn_port=9001, target_port=443)

        call_args, _ = self.mocked_cursor.execute.call_args
        sql, call_params = call_args
        expected_sql = 'SELECT conn_port, target_addr, target_name, target_port, target_component FROM ipam WHERE target_name LIKE (%s) AND target_addr LIKE (%s) AND target_component LIKE (%s) AND conn_port = (%s) AND target_port = (%s);'
        expected_params = ('myVM', '1.2.3.4', 'CEE', 9001, 443)

        self.assertEqual(sql, expected_sql)
        self.assertEqual(call_params, expected_params)

    def test_lookup_port_response(self):
        """``lookup_port`` returns the expected data structure"""
        self.mocked_cursor.fetchall.return_value = [(9001, '1.2.3.4', 'myVM', 'someComponent', 22),
                                                    (9008, '1.2.3.4', 'myVM', 'someComponent', 443)]

        db = database.Database()
        result = db.lookup_port()
        expected = {9001: {'name': 'myVM',
                           'target_addr': '1.2.3.4',
                           'target_port': 'someComponent',
                           'component': 22},
                    9008: {'name': 'myVM',
                           'target_addr': '1.2.3.4',
                           'target_port':
                           'someComponent',
                           'component': 443}}

        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
