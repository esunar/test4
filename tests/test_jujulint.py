#!/usr/bin/python3

import unittest

import jujulint


class TestJujuLint(unittest.TestCase):

    def test_flatten_list(self):
        unflattened_list = [1, [2, 3]]
        flattened_list = [1, 2, 3]
        self.assertEqual(flattened_list, jujulint.flatten_list(unflattened_list))

        unflattened_list = [1, [2, [3, 4]]]
        flattened_list = [1, 2, 3, 4]
        self.assertEqual(flattened_list, jujulint.flatten_list(unflattened_list))

    def test_map_charms(self):
        model = jujulint.ModelInfo()
        applications = {'test-app-1': {'charm': "cs:~USER/SERIES/TEST-CHARM12-123"},
                        'test-app-2': {'charm': "cs:~USER/TEST-CHARM12-123"},
                        'test-app-3': {'charm': "cs:TEST-CHARM12-123"},
                        'test-app-4': {'charm': "local:SERIES/TEST-CHARM12"},
                        'test-app-5': {'charm': "local:TEST-CHARM12"},
                        'test-app-6': {'charm': "cs:~TEST-CHARMERS/TEST-CHARM12-123"},
                        }
        jujulint.map_charms(applications, model)
        for charm in model.charms:
            self.assertEqual("TEST-CHARM12", charm)
        applications = {'test-app1': {'charm': "cs:invalid-charm$"}, }
        with self.assertRaises(jujulint.InvalidCharmNameError):
            jujulint.map_charms(applications, model)
