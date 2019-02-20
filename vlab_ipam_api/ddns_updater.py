# -*- coding: UTF-8 -*-
"""This script will send Dynamic DNS updates to the vLab DNS service"""
import time
import json
import fcntl
import socket
import struct

import dns.query
import dns.update
import dns.resolver
import dns.tsigkeyring
from setproctitle import setproctitle

from vlab_ipam_api.lib import const, get_logger

LOG_FILE = '/var/log/vlab_ipam_ddns_updater.log'
VLAB_KEYNAME = 'DDNS_UPDATE'


def get_ip(iface='ens160'):
    """Obtain the current IP of the WAN interface

    :Returns: String

    :param iface: The name of the network interface that owns the IP
    :type iface: String
    """
    interface = iface.encode()[:15] # Prevent lower lib from barfing over too long of iface name
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = fcntl.ioctl(s.fileno(),
                       0x8915, # SIOCGIFADDR - http://man7.org/linux/man-pages/man7/netdevice.7.html
                       struct.pack('256s', interface))
    ip = socket.inet_ntoa(data[20:24]) # the IPv4 addr is the 4 bytes in this range
    return ip


def get_hostname():
    """Obtain the hostname of this gateway"""
    name = socket.gethostname()
    return name.split('.')[0]


def get_ddns_key_info():
    """Obtain the DDNS key and algorithm from a JSON file

    Returns: Tuple (keyring, algorithm)
    """
    keyring = dns.tsigkeyring.from_text({VLAB_KEYNAME : const.VLAB_DDNS_KEY})
    return keyring, const.VLAB_DDNS_ALGORITHM


def update_a_record(hostname, ip, domain, domain_ip, keyring, algorithm):
    """Update the DNS record

    :Returns: None

    :param hostname: The name to give the DNS record
    :type hostname: String

    :param ip: The IP the hostname should map to
    :type ip: String

    :param domain: The FQDN of the vLab server
    :type domain: String

    :param domain_ip: The IPv4 address of the DNS server to send the udpate to
    :type domain_ip: String

    :param keyring: The dnssec creds required for making an update
    :type keyring: dns.tsigkeyring.from_text

    :type algorithm: The encryption method used for the keyring creds
    :type algorithm: String
    """
    update = dns.update.Update(domain, keyring=keyring, keyalgorithm=algorithm)
    update.replace(hostname, 300, 'a', ip) # 'a' means A-record, 300 is the TTL
    dns.query.udp(update, domain_ip)


def resolve_domain(domain):
    """Obtain the A record for the IP address of a given domain. This function
    exists because ``dns.query`` requires an IP.

    :Returns: String

    :Raises: RuntimeError

    :param domain: The FQDN to obtain the IP of
    :type domain: String
    """
    answer = dns.resolver.query(domain, 'a')
    if len(answer) != 1:
        raise RuntimeError('Multiple records for {} found: {}'.format(domain, len(answer)))
    else:
        return answer[0].to_text()


def main():
    """Entry point for script"""
    log = get_logger(name=__name__, log_file=LOG_FILE)
    log.info('DDNS updater starting')
    keyring, algorithm = get_ddns_key_info()
    domain = const.VLAB_URL.replace("https://", "").replace("http://", "")
    domain_ip = resolve_domain(domain)
    hostname = get_hostname()
    loop_interval = 5
    max_update_period = 120
    update_regardless = int(max_update_period / loop_interval)
    log.info('Checking for updated IP every {} seconds'.format(loop_interval))
    log.info('Sending DDNS update regardless of new IP every {} seconds'.format(max_update_period))
    current_ip = None
    count = 0
    log.info('Domain: {}'.format(domain))
    log.info('Domain IP: {}'.format(domain_ip))
    log.info('Hostname: {}'.format(hostname))
    log.info('DDNS KEY: {}'.format(const.VLAB_DDNS_KEY))
    log.info('Key Algorithm: {}'.format(algorithm))
    while True:
        start_time = time.time()
        new_ip = get_ip()
        if new_ip != current_ip:
            log.info('IP updated, was {}, now is {}'.format(current_ip, new_ip))
            try:
                update_a_record(hostname=hostname,
                                domain=domain,
                                domain_ip=domain_ip,
                                ip=new_ip,
                                keyring=keyring,
                                algorithm=algorithm)
            except Exception as doh:
                log.exception(doh)
            else:
                # Only update our ref to the IP if the DNS server accepted it
                current_ip = new_ip
                log.info('Updated IP, current IP is {}'.format(current_ip))
        else:
            # By updating every few minutes we allow the DNS server to be stateless
            # at the cost of eventual consistency; i.e. it'll break, but it'll
            # also resolve itself once all the gateways send the update.
            if count % update_regardless == 0:
                log.info('Sending DDNS update because it\'s been at least {} seconds since last update'.format(max_update_period))
                update_a_record(hostname=hostname,
                                domain=domain,
                                domain_ip=domain_ip,
                                ip=new_ip,
                                keyring=keyring,
                                algorithm=algorithm)
        count += 1
        elapsed_time = time.time() - start_time
        loop_delta = max(loop_interval - elapsed_time, 0) # avoid negative sleep
        log.debug('Will start next IP check in {} seconds'.format(loop_delta))
        time.sleep(loop_delta)


if __name__ == '__main__':
    setproctitle('IPAM-ddns-updater')
    main()
