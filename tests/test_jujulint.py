#!/usr/bin/python3

import unittest

import jujulint


class TestJujuLint(unittest.TestCase):

    def test_flatten_list(self):
        unflattened_list = [1, [2, 3]]
        flattened_list = [1, 2, 3]
        self.assertEqual(flattened_list, jujulint.flatten_list(unflattened_list))
