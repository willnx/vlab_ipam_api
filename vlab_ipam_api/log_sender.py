# -*- coding: UTF-8 -*-
"""This module uploads logs to a remote server"""
import time

import ujson
from kafka import KafkaProducer
from setproctitle import setproctitle
from cryptography.fernet import Fernet

from vlab_ipam_api.lib import const, get_logger

CIPHER_KEY_FILE = '/etc/vlab/log_sender.key'
NETFILTER_LOG_FILE = '/var/log/kern.log'
LOG_FILE = '/var/log/vlab_ipam_log_sender.log'
KAFKA_TOPIC = 'firewall'


def tail(a_file):
    """Like the Linux/Unix tail -f command

    :Returns: Generator

    :params a_file: The path to the file you want to follow/tail
    :type a_file: String
    """
    with open(a_file) as fp:
        fp.seek(0,2) # start at the end of the file
        while True:
            line = fp.readline()
            if not line:
                time.sleep(0.2)
            yield line


def get_cipher():
    """For encrypting uploaded data

    :Returns: cryptography.fernet.Fernet
    """
    with open(CIPHER_KEY_FILE, 'rb') as the_file:
        key = the_file.read().strip()
    cipher = Fernet(key)
    return cipher


def process_log_message(log_line, cipher, log):
    """Evaluate if the message is from Netfilter, and generate an encrypted payload

    If the supplied log message is not from Netfilter an empty stream of bytes is
    returned.

    :Returns: Bytes

    :param log_line: The log message to evaluate
    :type log_line: String

    :param cipher: The instantiated object for creating an encrypted payload
    :type cipher: cryptography.fernet.Fernet
    """
    source = None
    target = None
    date = None
    user = None
    message = b''
    if not log_line:
        return message
    # 2018-11-01T09:30:56.693495-04:00 HOSTNAME kernel: [   31.452226] IN=ens160 OUT=ens192 MAC=00:50:56:bc:5d:f8:00:50:56:bc:9a:1e:08:00 SRC=192.168.1.2 DST=65.200.22.114 LEN=40 TOS=0x00 TTL=63 ID=23104 DF PROTO=TCP SPT=48884 DPT=80 WINDOW=3472 RES=0x00 ACK FIN URGP=0
    chunks = log_line.split(' ')
    for chunk in chunks:
        if source and target:
            break
        elif chunk.startswith('SRC='):
            source = chunk.split('=')[-1]
        elif chunk.startswith('DST='):
            target = chunk.split('=')[-1]
    if source and target:
        user = const.VLAB_IPAM_OWNER
        date_string = chunks[0].split('.')[0] # strip off miliseconds and timezone
        pattern = '%Y-%m-%dT%H:%M:%S'
        try:
            epoch = int(time.mktime(time.strptime(date_string, pattern)))
        except ValueError:
            log.error('Invalid timestamp. Format: {}, Timestamp: {}'.format(pattern, date_string))
        else:
            payload = ujson.dumps({'time': epoch,
                                   'source': source,
                                   'target': target,
                                   'user' : user})
            log.debug(payload)
            message = cipher.encrypt(payload.encode()) # encode to turn into bytes
    return message


class Kafka(object):
    """Makes working with the public Kafka Producer more Pythonic"""
    def __init__(self, server, topic, log, retries=5):
        self._conn = KafkaProducer(bootstrap_servers=server, retries=retries)
        self._server = server
        self._topic = topic
        self._log = log
        self._log.info("Connection established to {}, topic: {}".format(self._server, self._topic))

    @property
    def topic(self):
        return self._topic

    def close(self):
        self._log.info("flushing any pending message uploads")
        self._conn.flush()
        self._log.info("terminating connection to {}".format(self._server))
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, the_traceback):
        self.close()

    def send(self, message):
        """Upload an encrypted message to Kafka

        :Returns: None

        :param message: The encrypted payload to upload
        :type message: Bytes
        """
        self._conn.send(self.topic, message)


def main():
    """Entry point logic"""
    log = get_logger(name=__name__, log_file=LOG_FILE)
    log.info('Starting Log Sender')
    cipher = get_cipher()
    with Kafka(server=const.VLAB_LOG_TARGET, topic=KAFKA_TOPIC, log=log) as kafka:
        for log_line in tail(NETFILTER_LOG_FILE):
            message = process_log_message(log_line, cipher, log)
            if message:
                kafka.send(message)
    log.info('Ending Log Sender')


if __name__ == '__main__':
    setproctitle('IPAM-log-sender')
    main()
