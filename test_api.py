import unittest
from api import app, server_config, timestamp

class CurlingTimerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_get(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_version(self):
        response = self.app.get('/version')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"version": {"value": server_config["version"].value}})

    def test_query_key(self):
        response = self.app.get('/config?key=num_ends')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"num_ends": server_config["num_ends"].value})

        response = self.app.get('/config?key=invalid_key')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"error": "Key not found"})

    def test_update_config(self):
        response = self.app.get('/update')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "No key provided"})

        response = self.app.get('/update?key=num_ends&value=10')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"num_ends": 10})

        response = self.app.get('/update?key=invalid_key&value=10')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {"error": "Key not found"})

    def test_start_timer(self):
        response = self.app.get('/start')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(server_config["is_timer_running"].value)

    def test_stop_timer(self):
        self.app.get('/start')
        response = self.app.get('/stop')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(server_config["is_timer_running"].value)

    def test_reset_timer(self):
        response = self.app.get('/reset')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(server_config["is_timer_running"].value)

    def test_get_times(self):
        response = self.app.get('/game_times')
        self.assertEqual(response.status_code, 200)
        self.assertIn("uptime", response.json)
        self.assertIn("num_ends", response.json)
        self.assertIn("time_per_end", response.json)

if __name__ == '__main__':
    unittest.main()