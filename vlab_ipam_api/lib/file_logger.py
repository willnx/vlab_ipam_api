# -*- coding: UTF-8 -*-
"""Module for creating log objects"""
import logging
from logging.handlers import RotatingFileHandler


def get_logger(name, log_file, loglevel='INFO'):
    """Simple factory function for creating logging objects

    :Returns: logging.Logger

    :param name: The name of the logger (typically just __name__).
    :type name: String

    :param loglevel: The verbosity of the logging; ERROR, INFO, DEBUG
    :type loglevel: String
    """
    logger = logging.getLogger(name)
    logger.setLevel(loglevel.upper())
    if not logger.handlers:
        ch = RotatingFileHandler(log_file, maxBytes=500000, backupCount=1)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setLevel(loglevel.upper())
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger
