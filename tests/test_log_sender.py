# -*- coding: UTF-8 -*-
"""A suite of tests for the log_sender.py module"""
import types
import unittest
from unittest.mock import patch, MagicMock, mock_open

from vlab_ipam_api import log_sender


class TestLogSender(unittest.TestCase):
    """A suite of test cases for the log_sender.py module"""
    @classmethod
    def setUpClass(cls):
        key = log_sender.Fernet.generate_key()
        cls.cipher = log_sender.Fernet(key)

    def test_tail_generator(self):
        """``tail`` returns a generator"""
        fake_fp = MagicMock()
        with patch("builtins.open", mock_open(mock=fake_fp)) as mock_file:
            logs = log_sender.tail('/some/log/file')
            next(logs)

        self.assertTrue(isinstance(logs, types.GeneratorType))

    def test_get_cipher(self):
        """``get_cipher`` returns an object for encrypting messages"""
        tmp_key = log_sender.Fernet.generate_key()
        with patch("builtins.open", mock_open(read_data=tmp_key)) as mock_file:
            cipher = log_sender.get_cipher()

        self.assertTrue(isinstance(cipher, log_sender.Fernet))

    def test_process_log_message(self):
        """``process_log_message`` returns an encrypted message"""
        # Truncated a lot of this example to increase readability
        fake_log = MagicMock()
        example_line = "2018-11-01T09:30:56.693495-04:00 IN=ens160 OUT=ens1 SRC=192.168.1.2 DST=10.1.1.1 WINDOW=3472 RES=0x00 "

        message = log_sender.process_log_message(example_line, self.cipher, fake_log)
        # Failure to decrypt will raise exception
        self.cipher.decrypt(message)

        self.assertTrue(isinstance(message, bytes))

    def test_process_log_message_empty(self):
        """``process_log_message`` bails early if supplied an empty log line"""
        fake_cipher = MagicMock()
        fake_line = ''
        fake_log = MagicMock()

        log_sender.process_log_message(fake_line, fake_cipher, fake_log)

        self.assertFalse(fake_cipher.encrypt.called)
        self.assertFalse(fake_log.error.called)

    def test_process_log_message_bad_timestamp(self):
        """``process_log_message`` returns an empty message if the line has a poorly formatted time stamp"""
        # Truncated a lot of this example to increase readability
        fake_log = MagicMock()
        example_line = "Nov 11 13:01:2 IN=ens160 OUT=ens1 SRC=192.168.1.2 DST=10.1.1.1 "

        message = log_sender.process_log_message(example_line, self.cipher, fake_log)
        expected = b''

        self.assertEqual(message, expected)

    @patch.object(log_sender, 'KafkaProducer')
    def test_kafka(self, fake_KafkaProducer):
        """``Kafka`` can be instantiated"""
        fake_log = MagicMock()
        k = log_sender.Kafka(server='localhost:9092', topic='someTopic', log=fake_log)

        self.assertTrue(isinstance(k, log_sender.Kafka))

    @patch.object(log_sender, 'KafkaProducer')
    def test_kafka_context_mgr(self, fake_KafkaProducer):
        """``Kafka`` supports use of the 'with' statement"""
        fake_log = MagicMock()
        try:
            with log_sender.Kafka(server='localhost:9092', topic='someTopic', log=fake_log) as k:
                pass
        except AttributeError:
            support_with_statement = False
        else:
            support_with_statement = True

        self.assertTrue(support_with_statement)

    @patch.object(log_sender, 'KafkaProducer')
    def test_kafka_closes(self, fake_KafkaProducer):
        """``Kafka`` auto-closed the socket when exiting the 'with' statement"""
        fake_conn = MagicMock()
        fake_KafkaProducer.return_value = fake_conn
        fake_log = MagicMock()

        with log_sender.Kafka(server='localhost:9092', topic='someTopic', log=fake_log) as k:
            pass

        self.assertTrue(fake_conn.close.called)

    @patch.object(log_sender, 'KafkaProducer')
    def test_kafka_flushes(self, fake_KafkaProducer):
        """``Kafka`` auto-closed the flushes pending messages when exiting the 'with' statement"""
        fake_conn = MagicMock()
        fake_KafkaProducer.return_value = fake_conn
        fake_log = MagicMock()

        with log_sender.Kafka(server='localhost:9092', topic='someTopic', log=fake_log) as k:
            pass

        self.assertTrue(fake_conn.flush.called)

    @patch.object(log_sender, 'KafkaProducer')
    def test_kafka_send(self, fake_KafkaProducer):
        """``Kafka.send`` pushes a message to the remote server"""
        fake_conn = MagicMock()
        fake_KafkaProducer.return_value = fake_conn
        fake_log = MagicMock()

        k = log_sender.Kafka(server='localhost:9092', topic='someTopic', log=fake_log)
        k.send(b'my message')

        self.assertTrue(fake_conn.send.called)

    @patch.object(log_sender, 'get_logger')
    @patch.object(log_sender, 'get_cipher')
    @patch.object(log_sender, 'KafkaProducer')
    @patch.object(log_sender, 'tail')
    def test_main(self, fake_tail, fake_KafkaProducer, fake_get_cipher, fake_get_logger):
        """``main`` returns None upon exit"""
        fake_tail.return_value = ['', '2018-11-01T09:30:56.693495-04:00 IN=ens160 OUT=ens1 SRC=192.168.1.2 DST=10.1.1.1']

        output = log_sender.main()
        expected = None

        self.assertEqual(output, expected)


if __name__ == '__main__':
    unittest.main()
