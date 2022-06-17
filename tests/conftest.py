#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2020 James Hebden <james.hebden@canonical.com>
#
# Distributed under terms of the GPL license.

"""Test fixtures for juju-lint tool."""

import os
import sys

import mock
import pytest

# bring in top level library to path
test_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_path + "/../")


@pytest.fixture
def mocked_pkg_resources(monkeypatch):
    """Mock the pkg_resources library."""
    import pkg_resources

    monkeypatch.setattr(pkg_resources, "require", mock.Mock())


@pytest.fixture
def cli(monkeypatch):
    """Provide a test instance of the CLI class."""
    monkeypatch.setattr(
        sys, "argv", ["juju-lint", "-c", "contrib/canonical-rules.yaml"]
    )

    from jujulint.cli import Cli

    cli = Cli()

    return cli


@pytest.fixture
def utils():
    """Provide a test instance of the CLI class."""
    from jujulint import util

    return util


@pytest.fixture
def parser(monkeypatch):
    """Mock the configuration parser."""
    monkeypatch.setattr("jujulint.config.ArgumentParser", mock.Mock())


@pytest.fixture
def linter(parser):
    """Provide test fixture for the linter class."""
    from jujulint.lint import Linter

    rules = {
        "known charms": ["ntp", "ubuntu"],
        "operations mandatory": ["ubuntu"],
        "subordinates": {
            "ntp": {"where": "all"},
        },
    }

    linter = Linter("mockcloud", "mockrules.yaml")
    linter.lint_rules = rules
    linter.collect_errors = True

    return linter


@pytest.fixture
def juju_status():
    """Provide a base juju status for testing."""
    return {
        "applications": {
            "ubuntu": {
                "application-status": {"current": "active"},
                "charm": "cs:ubuntu-18",
                "charm-name": "ubuntu",
                "relations": {"juju-info": ["ntp"]},
                "units": {
                    "ubuntu/0": {
                        "juju-status": {"current": "idle"},
                        "machine": "0",
                        "subordinates": {
                            "ntp/0": {
                                "juju-status": {"current": "idle"},
                                "workload-status": {"current": "active"},
                            }
                        },
                        "workload-status": {"current": "active"},
                    }
                },
            },
            "ntp": {
                "application-status": {"current": "active"},
                "charm": "cs:ntp-47",
                "charm-name": "ntp",
                "relations": {"juju-info": ["ubuntu"]},
            },
        },
        "machines": {
            "0": {
                "hardware": "availability-zone=rack-1",
                "juju-status": {"current": "started"},
                "machine-status": {"current": "running"},
                "modification-status": {"current": "applied"},
            },
            "1": {
                "hardware": "availability-zone=rack-2",
                "juju-status": {"current": "started"},
                "machine-status": {"current": "running"},
            },
            "2": {
                "hardware": "availability-zone=rack-3",
                "juju-status": {"current": "started"},
                "machine-status": {"current": "running"},
            },
        },
    }
