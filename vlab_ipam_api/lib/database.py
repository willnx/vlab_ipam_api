# -*- coding: UTF-8 -*-
"""This module creates a simpler way to work with the vLab IPAM database"""
import random

import psycopg2

from vlab_ipam_api.lib import const
from vlab_ipam_api.lib.exceptions import DatabaseError


class Database(object):
    """Simplifies communication with the database.

    The goal of this object is to make basic interactions with the database
    simpler than directly using the psycopg2 library. It does this by reducing
    the number of API methods, providing handy built-in methods for common needs
    (like listing tables of a database), auto-commit of transactions, and
    auto-rollback of bad SQL transactions.

    :param user: The username when connection to the database
    :type user: String, default postgres

    :param dbname: The specific database to connection to. InsightIQ utilizes
                   a different database for every monitored cluster, plus one
                   generic database for the application (named "insightiq").
    :type dbname: String, default insightiq
    """
    def __init__(self, user='postgres', dbname='vlab_ipam'):
        self._connection = psycopg2.connect(user=user, dbname=dbname)
        self._cursor = self._connection.cursor()

    def __enter__(self):
        """Enables use of the ``with`` statement to auto close database connection
        https://docs.python.org/2.7/reference/datamodel.html#with-statement-context-managers

        Example::

          with Database() as db:
              print(list(db.port_info(port_conn)))
        """
        return self

    def __exit__(self, exc_type, exc_value, the_traceback):
        self._connection.close()

    def execute(self, sql, params=None):
        """Run a single SQL command

        :Returns: List

        :param sql: **Required** The SQL syntax to execute
        :type sql: String

        :param params: The values to use in a parameterized SQL query
        :type params: Iterable
        """
        try:
            self._cursor.execute(sql, params)
            self._connection.commit()
        except psycopg2.Error as doh:
            # All psycopg2 Exceptions are subclassed from psycopg2.Error
            self._connection.rollback()
            raise DatabaseError(message=doh.pgerror, pgcode=doh.pgcode)
        else:
            if self._cursor.description is None:
                return []
            else:
                return self._cursor.fetchall()

    def close(self):
        """Disconnect from the database"""
        self._connection.close()

    def add_port(self, target_addr, target_port, target_name, target_component):
        """Create the record for a port mapping rule. Returns the local connection
        port that maps to the remote machine target port.

        :Returns: Integer

        :param target_addr: The IP address of the remote machine.
        :type target_addr: String

        :param target_port: The port on the remote machine to map to.
        :type target_port: Integer

        :param target_name: The human name given to the remote machine
        :type target_name: String

        :param target_component: The category/type of remote machine
        :type target_component: String
        """
        sql = """INSERT INTO ipam (conn_port, target_addr, target_port, target_name, target_component)\
                 VALUES (%s, %s, %s, %s, %s);"""
        for _ in range(const.VLAB_INSERT_MAX_TRIES):
            conn_port = random.randint(const.VLAB_PORT_MIN, const.VLAB_PORT_MAX)
            try:
                self.execute(sql=sql, params=(conn_port, target_addr, target_port, target_name, target_component))
            except DatabaseError as doh:
                if doh.pgcode == '23505':
                    # port already in use
                    continue
                else:
                    raise doh
            else:
                # insert worked
                break
        else:
            # max tries exceeded
            raise RuntimeError('Failed to create port map after %s tries' % const.VLAB_INSERT_MAX_TRIES)
        return conn_port

    def delete_port(self, conn_port):
        """Destroy a port mapping record

        :Returns: None

        :param conn_port: The local port connection that maps to a remote machine
        :type conn_port: Integer
        """
        sql = "DELETE FROM ipam WHERE conn_port=(%s);"
        self.execute(sql=sql, params=(conn_port,))

    def port_info(self, conn_port):
        """Obtain the remote port and remote address that a local port maps to.

        :Returns: Tuple

        :param conn_port: The local port connection that maps to a remote machine
        :type conn_port: Integer
        """
        sql = "SELECT conn_port, target_port, target_addr FROM ipam WHERE conn_port=(%s);"
        rows = list(self.execute(sql, params=(conn_port,)))
        if rows:
            target_port, target_addr = rows[0]
        else:
            target_port, target_addr = None, None
        return target_port, target_addr
