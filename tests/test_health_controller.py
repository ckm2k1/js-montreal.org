# -*- coding: utf-8 -*-
#
# test_health_controller.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

from tests import BaseTestCase
from borgy_process_agent import ProcessAgent
from borgy_process_agent_api_server.models.health_check import HealthCheck


class TestHealthController(BaseTestCase):
    """HealthController integration test stubs"""

    def test_v1_health_get_ready(self):
        """Test case when PA is not ready
        """
        print(self._pa._callback_jobs_provider)
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        print(self._pa._callback_jobs_provider)
        print(health)
        self.assertEqual(health.is_ready, False, "Should be not ready.")
        self.assertEqual(health.is_shutdown, False, "Should be not shutdown.")

        # Define callback for PA. Should be ready.
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, True, "Should be ready.")
        self.assertEqual(health.is_shutdown, False, "Should be not shutdown.")

        # Return None on callback for PA.
        # Return an empty array, and prepare next jobs in parallel.
        self._pa.set_callback_jobs_provider(lambda pa: None)
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Prepared jobs should define shutdown state.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, True, "Should be ready.")
        self.assertEqual(health.is_shutdown, True, "Should be shutdown.")

    def test_v1_health_get_multiple_pa_ready(self):
        """Test case when multiple PA is not ready
        """
        pa2 = ProcessAgent()
        pa2.set_autokill(False)
        pa2._insert()

        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, False, "Should be not ready.")
        self.assertEqual(health.is_shutdown, False, "Should be not shutdown.")

        # Define callback for second PA. Should be ready.
        pa2.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, True, "Should be ready.")
        self.assertEqual(health.is_shutdown, False, "Should be not shutdown.")

        # Define callback for first PA. Should be ready.
        self._pa.set_callback_jobs_provider(lambda pa: [])
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, True, "Should be ready.")
        self.assertEqual(health.is_shutdown, False, "Should be not shutdown.")

        # Return None on callback for first PA. Should be not shutdown yet.
        self._pa.set_callback_jobs_provider(lambda pa: None)
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, True, "Should be ready.")
        self.assertEqual(health.is_shutdown, False, "Should be not shutdown.")

        # Return None on callback for second PA.
        # Return an empty array, and prepare next jobs in parallel.
        pa2.set_callback_jobs_provider(lambda pa: None)
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        jobs_ops = response.get_json()
        self.assertIn('submit', jobs_ops)
        self.assertIn('rerun', jobs_ops)
        self.assertEqual(len(jobs_ops['submit']), 0)
        self.assertEqual(len(jobs_ops['rerun']), 0)

        # Wait end of jobs prepatation
        self._pa._prepare_job_thread.join()

        # Prepared jobs should define shutdown state.
        response = self.client.open('/v1/jobs', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        response = self.client.open('/v1/health', method='GET')
        self.assertStatus(response, 200, 'Should return 200. Response body is : ' + response.data.decode('utf-8'))
        health = HealthCheck.from_dict(response.get_json())
        self.assertEqual(health.is_ready, True, "Should be ready.")
        self.assertEqual(health.is_shutdown, True, "Should be shutdown.")

        pa2._remove()


if __name__ == '__main__':
    import unittest
    unittest.main()
