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


def test_map_charms(linter, utils):
    """Test the charm name validation code."""
    applications = {
        "test-app-1": {"charm": "cs:~USER/SERIES/TEST-CHARM12-123"},
        "test-app-2": {"charm": "cs:~USER/TEST-CHARM12-123"},
        "test-app-3": {"charm": "cs:TEST-CHARM12-123"},
        "test-app-4": {"charm": "local:SERIES/TEST-CHARM12"},
        "test-app-5": {"charm": "local:TEST-CHARM12"},
        "test-app-6": {"charm": "cs:~TEST-CHARMERS/TEST-CHARM12-123"},
    }
    linter.map_charms(applications)
    for charm in linter.model.charms:
        assert "TEST-CHARM12" == charm
    applications = {
        "test-app1": {"charm": "cs:invalid-charm$"},
    }
    with pytest.raises(utils.InvalidCharmNameError):
        linter.map_charms(applications)


class TestLinter:
    def test_minimal_rules(self, linter, juju_status):
        """Test that the base rules/status have no errors."""
        linter.do_lint(juju_status)
        assert len(linter.output_collector["errors"]) == 0

    def test_charm_identification(self, linter, juju_status):
        """Test that applications are mapped to charms."""
        juju_status["applications"]["ubuntu2"] = {
            "application-status": {"current": "active"},
            "charm-name": "ubuntu",
            "relations": {"juju-info": ["ntp"]},
            "units": {
                "ubuntu2/0": {
                    "juju-status": {"current": "idle"},
                    "machine": "1",
                    "subordinates": {
                        "ntp/1": {
                            "juju-status": {"current": "idle"},
                            "workload-status": {"current": "error"},
                        }
                    },
                    "workload-status": {"current": "active"},
                }
            },
        }
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "charm-not-mapped"
        assert errors[0]["application"] == "ubuntu2"

    def test_juju_status_unexpected(self, linter, juju_status):
        """Test that juju and workload status is expected."""
        # inject invalid status to the application
        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"][
            "workload-status"
        ].update(
            {
                "current": "error",
                "since": "01 Apr 2021 05:14:13Z",
                "message": 'hook failed: "install"',
            }
        )
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "status-unexpected"
        assert errors[0]["status_current"] == "error"
        assert errors[0]["status_since"] == "01 Apr 2021 05:14:13Z"
        assert errors[0]["status_msg"] == 'hook failed: "install"'

    def test_AZ_parsing(self, linter, juju_status):
        """Test that the AZ parsing is working as expected."""
        # duplicate a AZ name so we have 2 AZs instead of the expected 3
        juju_status["machines"]["2"]["hardware"] = "availability-zone=rack-1"
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "AZ-invalid-number"
        assert errors[0]["num_azs"] == 2

    def test_AZ_balancing(self, linter, juju_status):
        """Test that applications are balanced across AZs."""
        # add an extra machine in an existing AZ
        juju_status["machines"].update(
            {
                "3": {
                    "hardware": "availability-zone=rack-3",
                    "juju-status": {"current": "started"},
                    "machine-status": {"current": "running"},
                    "modification-status": {"current": "applied"},
                }
            }
        )
        # add two more ubuntu units, but unbalanced (ubuntu/0 is in rack-1)
        juju_status["applications"]["ubuntu"]["units"].update(
            {
                "ubuntu/1": {
                    "juju-status": {"current": "idle"},
                    "machine": "2",
                    "subordinates": {
                        "ntp/1": {
                            "juju-status": {"current": "idle"},
                            "workload-status": {"current": "error"},
                        }
                    },
                    "workload-status": {"current": "active"},
                },
                "ubuntu/2": {
                    "juju-status": {"current": "idle"},
                    "machine": "3",
                    "subordinates": {
                        "ntp/2": {
                            "juju-status": {"current": "idle"},
                            "workload-status": {"current": "error"},
                        }
                    },
                    "workload-status": {"current": "active"},
                },
            }
        )
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "AZ-unbalance"
        assert errors[0]["application"] == "ubuntu"
        assert errors[0]["num_units"] == 3
        assert errors[0]["az_map"] == "rack-1: 1, rack-2: 0, rack-3: 2"

    def test_ops_charm_missing(self, linter, juju_status):
        """Test that missing ops mandatory charms are detected."""
        # add a new mandatory ops charm
        linter.lint_rules["operations mandatory"].append("telegraf")
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "ops-charm-missing"
        assert errors[0]["charm"] == "telegraf"

    def test_unrecognised_charm(self, linter, juju_status):
        """Test that unrecognised charms are detected."""
        # drop 'ubuntu' from the known charms
        linter.lint_rules["known charms"] = ["ntp"]
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "unrecognised-charm"
        assert errors[0]["charm"] == "ubuntu"

    def test_ops_subordinate_missing(self, linter, juju_status):
        """Test that missing ops subordinate charms are detected."""
        # drop the subordinate unit
        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"]["subordinates"] = {}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "ops-subordinate-missing"
        assert errors[0]["principals"] == "ubuntu"
        assert errors[0]["subordinate"] == "ntp"

    def test_subordinate_extraneous(self, linter, juju_status):
        """Test that extraneous subordinate charms are detected."""
        # this check triggers on subordinates on containers that should only
        # be present in hosts
        linter.lint_rules["subordinates"]["ntp"]["where"] = "host only"
        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"][
            "machine"
        ] = "0/lxd/0"
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "subordinate-extraneous"
        assert errors[0]["principals"] == "ubuntu"
        assert errors[0]["subordinate"] == "ntp"

    def test_subordinate_duplicates(self, linter, juju_status):
        """Test that subordinate charms are not duplicated."""
        ntp0 = juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"][
            "subordinates"
        ]["ntp/0"]
        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"]["subordinates"][
            "ntp/1"
        ] = ntp0
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "subordinate-duplicate"
        assert errors[0]["machines"] == "0"
        assert errors[0]["subordinate"] == "ntp"

    def test_openstack_charm_missing(self, linter, juju_status):
        """Test that missing openstack mandatory charms are detected."""
        linter.cloud_type = "openstack"
        linter.lint_rules["openstack mandatory"] = ["keystone"]
        linter.lint_rules["operations openstack mandatory"] = ["ubuntu"]
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "openstack-charm-missing"
        assert errors[0]["charm"] == "keystone"

    def test_openstack_ops_charm_missing(self, linter, juju_status):
        """Test that missing openstack mandatory ops charms are detected."""
        linter.cloud_type = "openstack"
        linter.lint_rules["openstack mandatory"] = ["ubuntu"]
        linter.lint_rules["operations openstack mandatory"] = [
            "openstack-service-checks"
        ]
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "openstack-ops-charm-missing"
        assert errors[0]["charm"] == "openstack-service-checks"

    def test_kubernetes_charm_missing(self, linter, juju_status):
        """Test that missing kubernetes mandatory charms are detected."""
        linter.cloud_type = "kubernetes"
        linter.lint_rules["kubernetes mandatory"] = ["kubernetes-master"]
        linter.lint_rules["operations kubernetes mandatory"] = []
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "kubernetes-charm-missing"
        assert errors[0]["charm"] == "kubernetes-master"

    def test_kubernetes_ops_charm_missing(self, linter, juju_status):
        """Test that missing kubernetes mandatory charms are detected."""
        linter.cloud_type = "kubernetes"
        linter.lint_rules["kubernetes mandatory"] = []
        linter.lint_rules["operations kubernetes mandatory"] = ["ntp"]
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "kubernetes-ops-charm-missing"
        assert errors[0]["charm"] == "ntp"

    def test_config_eq(self, linter, juju_status):
        """Test the config condition 'eq'."""
        linter.lint_rules["config"] = {"ubuntu": {"fake-opt": {"eq": False}}}
        juju_status["applications"]["ubuntu"]["options"] = {"fake-opt": True}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "config-eq-check"
        assert errors[0]["application"] == "ubuntu"
        assert errors[0]["rule"] == "fake-opt"
        assert errors[0]["expected_value"] == False
        assert errors[0]["actual_value"] == True

    def test_config_gte(self, linter, juju_status):
        """Test the config condition 'gte'."""
        linter.lint_rules["config"] = {"ubuntu": {"fake-opt": {"gte": 3}}}
        juju_status["applications"]["ubuntu"]["options"] = {"fake-opt": 0}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "config-gte-check"
        assert errors[0]["application"] == "ubuntu"
        assert errors[0]["rule"] == "fake-opt"
        assert errors[0]["expected_value"] == 3
        assert errors[0]["actual_value"] == 0

    def test_config_isset_false(self, linter, juju_status):
        """Test the config condition 'isset' false."""
        linter.lint_rules["config"] = {"ubuntu": {"fake-opt": {"isset": False}}}
        juju_status["applications"]["ubuntu"]["options"] = {"fake-opt": 0}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "config-isset-check-false"
        assert errors[0]["application"] == "ubuntu"
        assert errors[0]["rule"] == "fake-opt"
        assert errors[0]["actual_value"] == 0

    def test_config_isset_true(self, linter, juju_status):
        """Test the config condition 'isset' true."""
        linter.lint_rules["config"] = {"ubuntu": {"fake-opt": {"isset": True}}}
        juju_status["applications"]["ubuntu"]["options"] = {}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "config-isset-check-true"
        assert errors[0]["application"] == "ubuntu"
        assert errors[0]["rule"] == "fake-opt"
