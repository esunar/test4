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
from pathlib import Path
from unittest.mock import MagicMock

import mock
import pytest

# bring in top level library to path
test_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_path + "/../")

from jujulint import cloud  # noqa: E402


@pytest.fixture
def mocked_pkg_resources(monkeypatch):
    """Mock the pkg_resources library."""
    import pkg_resources

    monkeypatch.setattr(pkg_resources, "require", mock.Mock())


@pytest.fixture
def cli_instance(monkeypatch):
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
def cloud_instance():
    """Provide a Cloud instance to test."""
    from jujulint.cloud import Cloud

    rules = {
        "known charms": ["nrpe", "ubuntu", "nagios"],
        "operations mandatory": ["nagios"],
    }
    cloud = Cloud(name="test_cloud", lint_rules=rules)
    # set initial cloud state
    cloud.cloud_state = {
        "my_controller": {"models": {"my_model_1": {}, "my_model_2": {}}}
    }
    cloud.logger = MagicMock()
    return cloud


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
                "endpoint-bindings": {
                    "": "external-space",
                    "certificates": "external-space",
                },
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
                "endpoint-bindings": {
                    "": "external-space",
                    "certificates": "external-space",
                },
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


@pytest.fixture
def juju_export_bundle():
    """Simulate a cloud with one controller and two bundles.

    my_model_1 nrpe offers the monitors endpoint
    my_model_2 nagios consumes the monitors endpoint from my_model_1
    """
    return {
        "my_model_1": [
            {
                "series": "focal",
                "saas": {"remote-2290e64ea1ac41858eb06a69b6a9d8cc": {}},
                "applications": {
                    "nrpe": {"charm": "nrpe", "channel": "stable", "revision": 86},
                    "ubuntu": {
                        "charm": "ubuntu",
                        "channel": "stable",
                        "revision": 19,
                        "num_units": 1,
                        "to": ["0"],
                        "constraints": "arch=amd64",
                    },
                },
                "machines": {"0": {"constraints": "arch=amd64"}},
                "relations": [
                    ["nrpe:general-info", "ubuntu:juju-info"],
                    [
                        "nrpe:monitors",
                        "remote-2290e64ea1ac41858eb06a69b6a9d8cc:monitors",
                    ],
                ],
            },
            {
                "applications": {
                    "nrpe": {
                        "offers": {
                            "nrpe": {
                                "endpoints": ["monitors"],
                                "acl": {"admin": "admin"},
                            }
                        }
                    }
                }
            },
        ],
        "my_model_2": [
            {
                "series": "bionic",
                "saas": {"nrpe": {"url": "my_controller:admin/my_model_1.nrpe"}},
                "applications": {
                    "nagios": {
                        "charm": "nagios",
                        "channel": "stable",
                        "revision": 49,
                        "num_units": 1,
                        "to": ["0"],
                        "constraints": "arch=amd64",
                    }
                },
                "machines": {"0": {"constraints": "arch=amd64"}},
                "relations": [["nagios:monitors", "nrpe:monitors"]],
            }
        ],
    }


@pytest.fixture()
def patch_cloud_init(mocker):
    """Patch objects needed in Cloud.__init__() method."""
    mocker.patch.object(cloud, "Logger")
    mocker.patch.object(cloud, "Connection")
    mocker.patch.object(cloud.socket, "getfqdn", return_value="localhost")


@pytest.fixture
def rules_files():
    """Get all standard rules files that comes with the snap."""
    return [
        str(rule.resolve()) for rule in Path("./contrib").iterdir() if rule.is_file()
    ]


@pytest.fixture
def juju_status_relation():
    """Representation of juju status input to test relations checks."""
    return {
        "nrpe-container": {
            "charm": "cs:nrpe-61",
            "charm-name": "nrpe",
            "relations": {
                "monitors": ["nagios"],
                "nrpe-external-master": [
                    "keystone",
                ],
            },
            "endpoint-bindings": {
                "general-info": "",
                "local-monitors": "",
                "monitors": "oam-space",
                "nrpe": "",
                "nrpe-external-master": "",
            },
        },
        "nrpe-host": {
            "charm": "cs:nrpe-67",
            "charm-name": "nrpe",
            "relations": {
                "monitors": ["nagios"],
                "nrpe-external-master": [
                    "elasticsearch",
                ],
            },
            "endpoint-bindings": {
                "general-info": "",
                "local-monitors": "",
                "monitors": "oam-space",
                "nrpe": "",
                "nrpe-external-master": "",
            },
        },
        "keystone": {
            "charm": "cs:keystone-309",
            "charm-name": "keystone",
            "relations": {
                "nrpe-external-master": ["nrpe-container"],
            },
            "endpoint-bindings": {
                "": "oam-space",
                "admin": "external-space",
                "certificates": "oam-space",
                "cluster": "oam-space",
                "domain-backend": "oam-space",
                "ha": "oam-space",
                "identity-admin": "oam-space",
                "identity-credentials": "oam-space",
                "identity-notifications": "oam-space",
                "identity-service": "oam-space",
                "internal": "internal-space",
                "keystone-fid-service-provider": "oam-space",
                "keystone-middleware": "oam-space",
                "nrpe-external-master": "oam-space",
                "public": "external-space",
                "shared-db": "internal-space",
                "websso-trusted-dashboard": "oam-space",
            },
        },
        "elasticsearch": {
            "charm": "cs:elasticsearch-39",
            "charm-name": "elasticsearch",
            "relations": {
                "nrpe-external-master": ["nrpe-host"],
            },
            "endpoint-bindings": {
                "": "oam-space",
                "client": "oam-space",
                "data": "oam-space",
                "logs": "oam-space",
                "nrpe-external-master": "oam-space",
                "peer": "oam-space",
            },
        },
    }
