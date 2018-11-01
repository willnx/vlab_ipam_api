# -*- coding: UTF-8 -*-
"""A suite of unit tests for the file_logger.py module"""
import unittest
from unittest.mock import patch, MagicMock

from vlab_ipam_api.lib import file_logger

class TestWorker(unittest.TestCase):
    """A suite of test cases for the file_logger.py module"""

    @patch.object(file_logger, 'RotatingFileHandler')
    def test_get_logger(self, fake_RotatingFileHandler):
        """``get_logger`` Returns a logging object"""
        logger = file_logger.get_logger(name='testing', log_file='/some/log/file.log')

        self.assertTrue(isinstance(logger, file_logger.logging.Logger))
