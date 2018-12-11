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
        applications = {'test-app-1': {'charm': "cs:~USER/SERIES/TEST-CHARM-123"},
                        'test-app-2': {'charm': "cs:~USER/TEST-CHARM-123"},
                        'test-app-3': {'charm': "cs:TEST-CHARM-123"},
                        'test-app-4': {'charm': "local:SERIES/TEST-CHARM"},
                        'test-app-5': {'charm': "local:./TEST-CHARM"},
                        }
        jujulint.map_charms(applications, model)
        for charm in model.charms:
            self.assertEqual("TEST-CHARM", charm)
