# coding: utf-8

"""
    RBVI ChimeraX Web Services

    REST API for RBVI web services supporting ChimeraX tools  # noqa: E501

    OpenAPI spec version: 0.1
    Contact: chimerax-users@cgl.ucsf.edu
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""

from __future__ import absolute_import

import unittest

import cxservices
from api.default_api import DefaultApi  # noqa: E501
from cxservices.rest import ApiException


class TestDefaultApi(unittest.TestCase):
    """DefaultApi unit test stubs"""

    def setUp(self):
        self.api = api.default_api.DefaultApi()  # noqa: E501

    def tearDown(self):
        pass

    def test_file_get(self):
        """Test case for file_get

        Return content of job file on server  # noqa: E501
        """
        pass

    def test_file_post(self):
        """Test case for file_post

        Upload job file to server  # noqa: E501
        """
        pass

    def test_files_get(self):
        """Test case for files_get

        Return job files on server as zip archive  # noqa: E501
        """
        pass

    def test_files_list(self):
        """Test case for files_list

        Return list of job files on server  # noqa: E501
        """
        pass

    def test_files_post(self):
        """Test case for files_post

        Upload zip archive of job files to server  # noqa: E501
        """
        pass

    def test_job_delete(self):
        """Test case for job_delete

        Delete job on server  # noqa: E501
        """
        pass

    def test_job_id(self):
        """Test case for job_id

        Return a new job identifier  # noqa: E501
        """
        pass

    def test_sleep(self):
        """Test case for sleep

        Sleep for a while and exit  # noqa: E501
        """
        pass

    def test_status(self):
        """Test case for status

        Return status of job  # noqa: E501
        """
        pass

    def test_submit(self):
        """Test case for submit

        Submit a job for execution  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()