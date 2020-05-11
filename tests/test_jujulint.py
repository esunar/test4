#!/usr/bin/python3
"""Tests for jujulint."""

import pytest
import jujulint

def test_flatten_list(utils):
    """Test the utils flatten_list function."""
    unflattened_list = [1, [2, 3]]
    flattened_list = [1, 2, 3]
    assert flattened_list == utils.flatten_list(unflattened_list)

    unflattened_list = [1, [2, [3, 4]]]
    flattened_list = [1, 2, 3, 4]
    assert flattened_list == utils.flatten_list(unflattened_list)


def test_map_charms(lint):
    """Test the charm name validation code."""
    applications = {'test-app-1': {'charm': "cs:~USER/SERIES/TEST-CHARM12-123"},
                    'test-app-2': {'charm': "cs:~USER/TEST-CHARM12-123"},
                    'test-app-3': {'charm': "cs:TEST-CHARM12-123"},
                    'test-app-4': {'charm': "local:SERIES/TEST-CHARM12"},
                    'test-app-5': {'charm': "local:TEST-CHARM12"},
                    'test-app-6': {'charm': "cs:~TEST-CHARMERS/TEST-CHARM12-123"},
                    }
    lint.map_charms(applications)
    for charm in lint.model.charms:
        assert "TEST-CHARM12" == charm
    applications = {'test-app1': {'charm': "cs:invalid-charm$"}, }
    with pytest.raises(jujulint.lint.InvalidCharmNameError):
        lint.map_charms(applications)
