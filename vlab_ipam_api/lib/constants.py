# -*- coding: UTF-8 -*-
"""
All the things can override via Environment variables are keep in this one file.

.. note::
    Any and all values that *are* passwords must contain the string 'AUTH' in
    the name of the constant. This is how we avoid logging passwords.
"""
from os import environ
import socket
from collections import namedtuple, OrderedDict


DEFINED = OrderedDict([
            ('VLAB_IPAM_LOG_LEVEL', environ.get('VLAB_IPAM_LOG_LEVEL', 'INFO')),
            ('VLAB_URL', environ.get('VLAB_URL', 'https://localhost')),
            # Only the owner of the firewall can make changes - see views for context
            ('VLAB_IPAM_OWNER', socket.gethostname().split('.')[0]),
            ('VLAB_PORT_MIN', int(environ.get('VLAB_PORT_MIN', 50000))),
            ('VLAB_PORT_MAX', int(environ.get('VLAB_PORT_MAX', 50100))),
            ('VLAB_INSERT_MAX_TRIES', int(environ.get('VLAB_INSERT_MAX_TRIES', 100))),
            ('VLAB_VERIFY_TOKEN', environ.get('VLAB_VERIFY_TOKEN', False)),
            ('VLAB_LOG_TARGET', environ.get('VLAB_LOG_TARGET', 'localhost:9092')),
            ('VLAB_DDNS_KEY', environ.get('VLAB_DDNS_KEY', 'PpULFMK6UQXYhFUot++fhNcmAumx+N7GcRfzO75NgL6RBA3gdJrw1KwraVR4QkhNoL23ySpdgTpWA1dUke2ZsA==')),
            ('VLAB_DDNS_ALGORITHM', environ.get('VLAB_DDNS_ALGORITHM', 'HMAC-SHA512')),
          ])

Constants = namedtuple('Constants', list(DEFINED.keys()))

# The '*' expands the list, just liked passing a function *args
const = Constants(*list(DEFINED.values()))
