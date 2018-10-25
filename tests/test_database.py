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


if __name__ == '__main__':
    unittest.main()
