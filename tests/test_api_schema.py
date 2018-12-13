# -*- coding: UTF-8 -*-
"""
A suite of tests for the HTTP API schemas
"""
import unittest

from jsonschema import Draft4Validator, validate, ValidationError
from vlab_ipam_api.lib.views import portmap, addr


class TestIpamViewSchema(unittest.TestCase):
    """A set of test cases for the schemas of /api/1/ipam/portmap"""

    def test_post_schema(self):
        """The schema defined for POST on is valid"""
        try:
            Draft4Validator.check_schema(portmap.PortMapView.POST_SCHEMA)
            schema_valid = True
        except RuntimeError:
            schema_valid = False

        self.assertTrue(schema_valid)


    def test_get_schema(self):
        """The schema defined for GET on is valid"""
        try:
            Draft4Validator.check_schema(portmap.PortMapView.GET_ARGS_SCHEMA)
            schema_valid = True
        except RuntimeError:
            schema_valid = False

        self.assertTrue(schema_valid)

    def test_delete_schema(self):
        """The schema defined for DELETE on is valid"""
        try:
            Draft4Validator.check_schema(portmap.PortMapView.DELETE_SCHEMA)
            schema_valid = True
        except RuntimeError:
            schema_valid = False

        self.assertTrue(schema_valid)


class TestAddrViewSchema(unittest.TestCase):
    """A set of test cases for the schemas of /api/1/ipam/addr"""

    def test_get_args(self):
        """The schema defined for the query params on GET is valid"""
        try:
            Draft4Validator.check_schema(addr.AddrView.GET_ARGS_SCHEMA)
            schema_valid = True
        except RuntimeError:
            schema_valid = False

        self.assertTrue(schema_valid)


if __name__ == '__main__':
    unittest.main()
