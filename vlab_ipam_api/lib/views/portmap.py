# -*- coding: UTF-8 -*-
"""
Defines the RESTful API for managing Port Map rules in the NAT firewall
"""
import random

import ujson
from flask import current_app
from flask_classy import request, Response
from vlab_api_common import BaseView, describe, get_logger, requires, validate_input

from vlab_ipam_api.lib import const, Database
from vlab_ipam_api.lib.exceptions import DatabaseError, CliError

logger = get_logger(__name__, loglevel=const.VLAB_IPAM_LOG_LEVEL)


class PortMapView(BaseView):
    """API end point for managing Port Map rules"""
    route_base = '/api/1/ipam/portmap'
    POST_SCHEMA = { "$schema": "http://json-schema.org/draft-04/schema#",
                    "type": "object",
                    "description": "Create port mapping to connect through a NAT firewall",
                    "properties": {
                        "target_addr": {
                            "description": "The IP of the machine in your lab to connect to",
                            "type": "string"
                        },
                        "target_port": {
                            "description": "The port number of the machine in your lab to connect to",
                            "type": "integer"
                        },
                        "target_name": {
                            "description": "The name of your component",
                            "type": "string"
                        },
                        "target_component": {
                            "description": "The kind of component (i.e. OneFS, InsightIQ, etc)",
                            "type": "string"
                        }
                    },
                    "required": ["target_addr", "target_port", "target_name", "target_component"]
                  }
    DELETE_SCHEMA = {"$schema": "http://json-schema.org/draft-04/schema#",
                     "description": "Destroy a port mapping",
                     "type": "object",
                     "properties": {
                        "conn_port": {
                            "description": "The local port that forwards into the user's lab",
                            "type": "integer"
                        }
                     },
                     "required": ["conn_port"]
                    }
    GET_ARGS_SCHEMA = {"$schema": "http://json-schema.org/draft-04/schema#",
                  "type": "object",
                  "description": "Display details about the port map rules configured",
                  "properties" : {
                      "name": {
                         "type": "string",
                         "description": "Filter results by VM name"
                      },
                      "target_addr" : {
                         "type": "string",
                         "description": "Filter results by VM IP address"
                      },
                      "target_port" : {
                         "type" : "integer",
                         "description": "Filter results by the target's port"
                      },
                      "component": {
                         "type": "string",
                         "description": "Filter results by VM type (i.e. OneFS, InsightIQ, etc)"
                      },
                      "conn_port": {
                         "type": "integer",
                         "description": "Filter results by the connection port"
                      }
                  },
                 }

    @requires(version=2, username=const.VLAB_IPAM_OWNER, verify=const.VLAB_VERIFY_TOKEN)
    @describe(post=POST_SCHEMA, delete=DELETE_SCHEMA, get_args=GET_ARGS_SCHEMA)
    def get(self, *args, **kwargs):
        """Display the Port Map rules defined on the NAT firewall"""
        username = kwargs['token']['username']
        resp_data = {'user' : username, 'content' : {}}
        status_code = 200
        name = request.args.get('name', None)
        addr = request.args.get('target_addr', None)
        component = request.args.get('component', None)
        conn_port = request.args.get('conn_port', 0)
        target_port = request.args.get('target_port', 0)
        conn_port, target_port, error = cast_port_values(conn_port, target_port)
        if error:
            resp_data['error'] = error
            resp = Response(ujson.dumps(resp_data))
            resp.status_code = 400
            return resp
        try:
            with Database() as db:
                resp_data['content'] = db.lookup_port(name=name, addr=addr,
                                                      component=component,
                                                      conn_port=conn_port,
                                                      target_port=target_port)
        except Exception as doh:
            logger.exception(doh)
            resp_data['error'] = '%s' % doh
            status_code = 500
        resp = Response(ujson.dumps(resp_data))
        resp.status_code = status_code
        return resp

    @requires(version=2, username=const.VLAB_IPAM_OWNER, verify=const.VLAB_VERIFY_TOKEN)
    @validate_input(schema=POST_SCHEMA)
    def post(self, *args, **kwargs):
        """Create a Port Map rule in the NAT firewall"""
        username = kwargs['token']['username']
        resp_data = {'user' : username, 'content' : {}}
        target_addr = kwargs['body']['target_addr']
        target_port = kwargs['body']['target_port']
        target_name = kwargs['body']['target_name']
        target_component = kwargs['body']['target_component']
        status_code = 200
        try:
            db = Database()
        except Exception as doh:
            status_code = 500
            resp_data['error'] = '%s' % doh
            logger.exception(doh)
        else:
            try:
                conn_port = db.add_port(target_addr, target_port, target_name, target_component)
                current_app.firewall.map_port(conn_port, target_port, target_addr)
            except Exception as doh:
                db.delete_port(conn_port)
                resp_data['error'] = '%s' % doh
                logger.exception(doh)
                status_code = 500
            else:
                resp_data['content']['conn_port'] = conn_port
            finally:
                db.close()

        resp = Response(ujson.dumps(resp_data))
        resp.status_code = status_code
        return resp

    @requires(version=2, username=const.VLAB_IPAM_OWNER, verify=const.VLAB_VERIFY_TOKEN)
    @validate_input(schema=DELETE_SCHEMA)
    def delete(self, *args, **kwargs):
        """Destroy a Port Map rule in the NAT firewall"""
        username = kwargs['token']['username']
        resp_data = {'user' : username, 'content' : {}}
        conn_port = kwargs['body']['conn_port']
        status_code = 200
        try:
            with Database() as db:
                target_port, target_addr = db.port_info(conn_port)
                # The ``with`` statement locks the firewall object
                # Only locking here because deleting requires multiple updates
                with current_app.firewall:
                    nat_id = current_app.firewall.find_rule(target_port, target_addr, table='nat', conn_port=conn_port)
                    filter_id = current_app.firewall.find_rule(target_port, target_addr, table='filter')
                    record_error, status_code = records_valid(nat_id, filter_id, target_port, target_addr)
                    if not record_error:
                        error, status_code = remove_port_map(nat_id, filter_id, target_port, target_addr, conn_port, db)
        except Exception as doh:
            logger.exception(doh)
            resp_data['error'] = '%s' % doh
            status_code = 500
        else:
            resp_data['error'] = error
        resp = Response(ujson.dumps(resp_data))
        resp.status_code = status_code
        return resp


def cast_port_values(conn_port_value, target_port_value):
    """Convert (if needed) a supplied port value into an integer. If unable to
    cast both values, an error message is returned.

    :Returns: Tuple (conn_port, target_port, error)

    :param conn_port_value:
    :type conn_port_value: Castable to Int

    :param target_port_value:
    :type target_port_value: Castable to Int
    """
    error = None
    try:
        conn_port_value = int(conn_port_value)
    except Exception:
        error = 'Param conn_port must be a number, supplied: {}'.format(conn_port_value)
    try:
        target_port_value = int(target_port_value)
    except Exception:
        error = 'Param target_port must be a number, supplied: {}'.format(conn_port_value)
    return conn_port_value, target_port_value, error


def records_valid(nat_id, filter_id, target_port, target_addr):
    """Ensure that the port is mapped, and the mapping records are consistent.

    :Returns: Tuple (Error Message, HTTP status code)

    :param nat_id: The ID for the rule to delete from the nat table.
    :type nat_id: String

    :param filter_id: The ID for the rule to delete from the filter table.
    :type filter_id: String

    :param target_port: The network port on the remote machine to connect to
    :type target_port: String

    :param target_addr: The IP address of the remote machine
    :type target_addr: String
    """
    if (target_port and target_addr) and not (nat_id and filter_id):
        return "DB record exist, but no iptable record; contact admin.", 500
    elif not (target_port and target_addr) and (nat_id and filter_id):
        return "iptable record exist, but no DB record; contact admin.", 500
    elif not (target_port and target_addr and nat_id and filter_id):
        return "No such port mapping record", 404
    else:
        return "", 200


def remove_port_map(nat_id, filter_id, target_port, target_addr, conn_port, db):
    """Delete a port mapping from the firewall.

    Caller must obtain a lock on the firewall before calling this function. If
    this function fails for any reason to completely delete the port mapping,
    it will re-create any deleted rules or records.

    :Returns: None

    :param nat_id: The ID for the rule to delete from the nat table.
    :type nat_id: String

    :param filter_id: The ID for the rule to delete from the filter table.
    :type filter_id: String

    :param target_port: The network port on the remote machine to connect to
    :type target_port: String

    :param target_addr: The IP address of the remote machine
    :type target_addr: String

    :param conn_port: The local port that maps to a remote port on a remote machine
    :type conn_port: Integer

    :param db: An instantiated connection to the IPAM database
    :type db: vlab_ipam_api.lib.database.Database
    """
    current_app.firewall.delete_rule(nat_id, table='nat')
    try:
        # If we fail to delete the 2nd rule, undo the 1st delete
        current_app.firewall.delete_rule(filter_id, table='filter')
        error = None
        status_code = 200
    except Exception as doh:
        status_code = 500
        error = '%s' % doh
        logger.exception(doh)
        current_app.firewall.forward(target_port, target_addr)
        current_app.firewall.save_rules()
    else:
        # iptables updated; let's update the DB
        try:
            db.delete_port(conn_port)
        except Exception as doh:
            # If (for whatever reason) the DB update fails, we must
            # restore the state of iptables
            current_app.firewall.map_port(conn_port, target_port, target_addr)
            status_code = 500
            error = '%s' % doh
            logger.exception(doh)
    return error, status_code
