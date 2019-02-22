#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
A RESTful API for automated IPAM of a personal lab in vLab
"""
from setuptools import setup, find_packages


setup(name="vlab-ipam-api",
      author="Nicholas Willhite,",
      author_email='willnx84@gmail.com',
      version='2019.02.22',
      packages=find_packages(),
      include_package_data=True,
      classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
      ],
      package_files={'vlab_ipam_api' : ['app.ini']},
      description="A RESTful API for automated IPAM of a personal lab in vLab",
      long_description=open('README.rst').read(),
      install_requires=['flask', 'pyjwt', 'uwsgi', 'vlab-api-common', 'psycopg2',
                        'ujson', 'cryptography', 'setproctitle', 'kafka-python',
                        'dnspython']
      )
