# -*- coding: UTF-8 -*-
"""
A RESTful API for looking up IP address information
"""
import socket

import ujson
from flask_classy import request, Response
from vlab_api_common import BaseView, describe, get_logger, requires

from vlab_ipam_api.lib import const, Database
from vlab_ipam_api.lib.exceptions import DatabaseError

logger = get_logger(__name__, loglevel=const.VLAB_IPAM_LOG_LEVEL)


class AddrView(BaseView):
    """API end point for looking up IP address information"""
    route_base = '/api/1/ipam/addr'
    GET_ARGS_SCHEMA = {"$schema": "http://json-schema.org/draft-04/schema#",
                       "type": "object",
                       "description": "Lookup IP addresses and related meta-data. Parameters are mutually exclusive.",
                       "properties" : {
                           "name" : {
                               "description": "Obtain the IP address of a component by name",
                               "type": "string"
                           },
                           "addr" : {
                               "description": "Obtain the name and component type by supplying the IP address",
                               "type": "string"
                           },
                           "component": {
                               "description": "Obtain the IP addresses and names of machines of a supplied component type",
                               "type": "string"
                           }
                       },
                      }

    @requires(version=2, verify=const.VLAB_VERIFY_TOKEN)
    @describe(get_args=GET_ARGS_SCHEMA)
    def get(self, *args, **kwargs):
        """Display the Port Map rules defined on the NAT firewall"""
        username = kwargs['token']['username']
        resp_data = {'user' : username, 'content' : {}}
        status_code = 200
        name = request.args.get('name', None)
        addr = request.args.get('addr', '')
        component = request.args.get('component', None)
        if args_valid(name=name, addr=addr, component=component):
            with Database() as db:
                resp_data['content'] = db.lookup_addr(name=name, addr=addr, component=component)
        else:
            resp_data['error'] = 'Params are mutually exclusive. Supplied: name={}, addr={}, component={}'.format(name, addr, component)
            status_code = 400
        resp = Response(ujson.dumps(resp_data))
        resp.status_code = status_code
        return resp


def args_valid(name, addr, component):
    """Validate that the supplied query parameters are OK.

    :Returns: Boolean

    :param name: The specific name of a machine in the lab to lookup the address of.
    :type name: String

    :param addr: The IP address to lookup meta data about.
    :type addr: String

    :param component: The type of vLab component to look up (i.e. OneFS, ESRS, etc)
    :type component: String
    """
    ok = True
    # Verify mutually exclusivity
    if (name and addr and component):
        ok = False
    elif (name and addr) or (name and component) or (addr and component):
        ok =  False
    # Verify addr is an IPv4 address
    if addr:
        try:
            socket.inet_aton(addr)
        except (OSError, TypeError):
            ok =  False
    return ok
