#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2020 James Hebden <james.hebden@canonical.com>
#
# Distributed under terms of the GPL license.

"""Test fixtures for juju-lint tool."""

import mock
import os
import pytest
import sys

# bring in top level library to path
test_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_path + '/../')


@pytest.fixture
def mocked_pkg_resources(monkeypatch):
    """Mock the pkg_resources library."""
    import pkg_resources

    monkeypatch.setattr(pkg_resources, 'require', mock.Mock())


@pytest.fixture
def cli():
    """Provide a test instance of the CLI class."""
    from jujulint.cli import Cli
    cli = Cli()

    return cli


@pytest.fixture
def utils():
    """Provide a test instance of the CLI class."""
    from jujulint import util
    return util


@pytest.fixture
def lint():
    """Provide test fixture for the linter class."""
    from jujulint.lint import Linter
    linter = Linter()

    return linter
