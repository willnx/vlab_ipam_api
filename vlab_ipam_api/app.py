# -*- coding: UTF-8 -*-
from flask import Flask

from vlab_ipam_api.lib import const
from vlab_ipam_api.lib.views import HealthView, PortMapView, AddrView
from vlab_ipam_api.lib.firewall import FireWall


app = Flask(__name__)
app.firewall = FireWall() # Attach to app, and call within views via ``current_app``

AddrView.register(app)
HealthView.register(app)
PortMapView.register(app)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
