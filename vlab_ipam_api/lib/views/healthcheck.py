# -*- coding: UTF-8 -*-
"""
Enables Health checks for the power API
"""
from time import time
import pkg_resources

import ujson
from flask_classy import FlaskView, Response


from vlab_ipam_api.lib import Database, firewall

class HealthView(FlaskView):
    """
    Simple end point to test if the service is alive
    """
    route_base = '/api/1/ipam/healthcheck'
    trailing_slash = False

    def get(self):
        """End point for health checks"""
        resp = {}
        status = 200
        resp['version'] = pkg_resources.get_distribution('vlab-ipam-api').version
        fwall = firewall.FireWall()
        try:
            with Database() as db:
                resp['database'] = list(db.execute("select * from ipam;"))
            resp['firewall'] = {}
            resp['firewall']['nat'] = fwall.show(table='nat', format='raw')
            resp['firewall']['filter'] = fwall.show(table='filter', format='raw')
        except Exception as doh:
            resp['error'] = '%s' % doh
            status = 500
        response = Response(ujson.dumps(resp))
        response.status_code = status
        response.headers['Content-Type'] = 'application/json'
        return response
