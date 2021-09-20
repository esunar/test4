#!/usr/bin/python3
"""Tests for jujulint."""
from datetime import datetime, timezone

import pytest


class TestUtils:
    """Test the jujulint utilities."""

    def test_flatten_list(self, utils):
        """Test the utils flatten_list function."""
        unflattened_list = [1, [2, 3]]
        flattened_list = [1, 2, 3]
        assert flattened_list == utils.flatten_list(unflattened_list)

        unflattened_list = [1, [2, [3, 4]]]
        flattened_list = [1, 2, 3, 4]
        assert flattened_list == utils.flatten_list(unflattened_list)

    def test_flatten_list_non_list_iterable(self, utils):
        """Test the utils flatten_list function."""
        iterable = {1: 2}
        assert iterable == utils.flatten_list(iterable)

    def test_is_container(self, utils):
        """Test the utils is_container function."""
        assert utils.is_container("1/lxd/0") is True
        assert utils.is_container("0") is False

    def test_is_virtual_machine(self, utils):
        """Test the utils is_virtual_machine function."""
        machine = "0"
        machine_data = {
            "hardware": "arch=amd64 cores=2 mem=4096M tags=virtual,pod-console-logging,vault availability-zone=AZ3"
        }
        assert utils.is_virtual_machine(machine, machine_data) is True

        machine_data = {}
        assert utils.is_virtual_machine(machine, machine_data) is False

    def test_is_metal(self, utils):
        """Test the utils is_metal function."""
        # A VM should return false
        machine = "0"
        machine_data = {
            "hardware": "arch=amd64 cores=2 mem=4096M tags=virtual,pod-console-logging,vault availability-zone=AZ3"
        }
        assert utils.is_metal(machine, machine_data) is False

        # A container should return false
        assert utils.is_metal("1/lxd/0", {}) is False

        # A bare metal should return true
        machine = "1"
        machine_data = {
            "hardware": "arch=amd64 cores=128 mem=2093056M tags=foundation-nodes,hyper-converged-az2 "
            "availability-zone=AZ2"
        }
        assert utils.is_metal(machine, machine_data) is True


class TestLinter:
    """Test the main Linter class."""

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

    def test_map_charms(self, linter, utils):
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

    def test_juju_status_unexpected(self, linter, juju_status):
        """Test that juju and workload status is expected."""
        # inject invalid status to the application
        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"][
            "workload-status"
        ].update(
            {
                "current": "executing",
                "since": "01 Apr 2021 05:14:13Z",
                "message": 'hook failed: "install"',
            }
        )
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "status-unexpected"
        assert errors[0]["status_current"] == "executing"
        assert errors[0]["status_since"] == "01 Apr 2021 05:14:13Z"
        assert errors[0]["status_msg"] == 'hook failed: "install"'

    def test_juju_status_ignore_recent_executing(self, linter, juju_status):
        """Test that recent executing status is ignored."""
        # inject a recent execution status to the unit
        since_datetime = datetime.now(timezone.utc)

        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"][
            "workload-status"
        ].update(
            {
                "current": "executing",
                "since": since_datetime.isoformat(),
                "message": 'hook failed: "install"',
            }
        )
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 0

    def test_az_parsing(self, linter, juju_status):
        """Test that the AZ parsing is working as expected."""
        # duplicate a AZ name so we have 2 AZs instead of the expected 3
        juju_status["machines"]["2"]["hardware"] = "availability-zone=rack-1"
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "AZ-invalid-number"
        assert errors[0]["num_azs"] == 2

    def test_az_balancing(self, linter, juju_status):
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

    def test_subordinate_duplicates_allow(self, linter, juju_status):
        """
        Test the subordinate option "allow-multiple".

        Setting it to true will skip the duplicate check for subordinates
        """
        template_status = {
            "juju-status": {"current": "idle"},
            "workload-status": {"current": "active"},
        }

        # Drop the fixture ntp rule and add the nrpe rule with allowing duplicates
        linter.lint_rules["subordinates"].pop("ntp")
        linter.lint_rules["subordinates"]["nrpe"] = {
            "where": "container aware",
            "host-suffixes": "[host, physical, guest]",
            "allow-multiple": True,
        }

        # Add a nrpe-host subordinate application
        linter.lint_rules["known charms"].append("nrpe")
        juju_status["applications"]["nrpe-host"] = {
            "application-status": {"current": "active"},
            "charm": "cs:nrpe-74",
            "charm-name": "nrpe",
            "relations": {"juju-info": ["ubuntu", "ubuntu2"]},
        }

        # Add a nrpe-host subordinate unit to the 'ubuntu' app
        juju_status["applications"]["ubuntu"]["units"]["ubuntu/0"]["subordinates"] = {
            "nrpe-host/0": template_status
        }

        # Add a second 'ubuntu' app with nrpe subordinate
        juju_status["applications"]["ubuntu2"] = {
            "application-status": {"current": "active"},
            "charm": "cs:ubuntu-18",
            "charm-name": "ubuntu",
            "relations": {"juju-info": ["ntp", "nrpe-host"]},
            "units": {
                "ubuntu2/0": {
                    "juju-status": {"current": "idle"},
                    "machine": "0",
                    "subordinates": {"nrpe-host/1": template_status},
                    "workload-status": {"current": "active"},
                }
            },
        }

        linter.do_lint(juju_status)

        # Since we allow duplicates there should be no errors
        errors = linter.output_collector["errors"]
        assert not errors

    def test_ops_subordinate_metal_only1(self, linter, juju_status):
        """
        Test that missing ops subordinate charms are detected.

        Use the "metal only" rule in a bare metal machine, should report the
        missing subordinate
        """
        linter.lint_rules["subordinates"]["hw-health"] = {"where": "metal only"}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "ops-subordinate-missing"
        assert errors[0]["principals"] == "ubuntu"
        assert errors[0]["subordinate"] == "hw-health"

    def test_ops_subordinate_metal_only2(self, linter, juju_status):
        """
        Test that missing ops subordinate charms are detected.

        Use the "metal only" rule in a VM, should ignore it
        """
        linter.lint_rules["subordinates"]["hw-health"] = {"where": "metal only"}

        # Turn machine "0" into a "VM"
        juju_status["machines"]["0"][
            "hardware"
        ] = "tags=virtual availability-zone=rack-1"
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert not errors

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
        juju_status["applications"].pop("ntp")  # drop the app from the model
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
        assert errors[0]["expected_value"] is False
        assert errors[0]["actual_value"] is True

    def test_config_neq_valid(self, linter, juju_status):
        """Test the config condition 'neq'."""
        linter.lint_rules["config"] = {"ubuntu": {"fake-opt": {"neq": "foo"}}}
        juju_status["applications"]["ubuntu"]["options"] = {"fake-opt": "bar"}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 0

    def test_config_neq_invalid(self, linter, juju_status):
        """Test the config condition 'neq', valid."""
        linter.lint_rules["config"] = {"ubuntu": {"fake-opt": {"neq": ""}}}
        juju_status["applications"]["ubuntu"]["options"] = {"fake-opt": ""}
        linter.do_lint(juju_status)

        errors = linter.output_collector["errors"]
        assert len(errors) == 1
        assert errors[0]["id"] == "config-neq-check"
        assert errors[0]["application"] == "ubuntu"
        assert errors[0]["rule"] == "fake-opt"
        assert errors[0]["expected_value"] == ""
        assert errors[0]["actual_value"] == ""

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

    def test_parse_cmr_apps_export_bundle(self, linter):
        """Test the charm CMR parsing for bundles."""
        parsed_yaml = {
            "saas": {
                "grafana": {"url": "foundations-maas:admin/lma.grafana"},
                "nagios": {"url": "foundations-maas:admin/lma.nagios-monitors"},
            }
        }
        linter.parse_cmr_apps(parsed_yaml)
        assert linter.model.cmr_apps == {"grafana", "nagios"}

    def test_parse_cmr_apps_jsfy(self, linter):
        """Test the charm CMR parsing for juju status."""
        parsed_yaml = {
            "application-endpoints": {
                "grafana": {"url": "foundations-maas:admin/lma.grafana"},
                "nagios": {"url": "foundations-maas:admin/lma.nagios-monitors"},
            }
        }
        linter.parse_cmr_apps(parsed_yaml)
        assert linter.model.cmr_apps == {"grafana", "nagios"}

    def test_parse_cmr_apps_libjuju(self, linter):
        """Test the charm CMR parsing for libjuju."""
        parsed_yaml = {
            "remote-applications": {
                "grafana": {"url": "foundations-maas:admin/lma.grafana"},
                "nagios": {"url": "foundations-maas:admin/lma.nagios-monitors"},
            }
        }
        linter.parse_cmr_apps(parsed_yaml)
        assert linter.model.cmr_apps == {"grafana", "nagios"}

    def test_check_charms_ops_mandatory_crm_success(self, linter):
        """
        Test the logic for checking ops mandatory charms provided via CMR.

        The app is in the saas rules and has a CMR, no error is expected
        """
        linter.lint_rules["saas"] = ["grafana"]
        linter.model.cmr_apps.add("grafana")
        error = linter.check_charms_ops_mandatory("grafana")

        assert error is None

    def test_check_charms_ops_mandatory_crm_fail1(self, linter):
        """
        Test the logic for checking ops mandatory charms provided via CMR.

        The app is not in the saas rules, should report an error
        """
        linter.model.cmr_apps.add("grafana")
        error = linter.check_charms_ops_mandatory("grafana")

        # The app is not in the rules, should report an error
        assert error is not None
        assert error["id"] == "ops-charm-missing"
        assert error["charm"] == "grafana"

    def test_check_charms_ops_mandatory_crm_fail2(self, linter):
        """
        Test the logic for checking ops mandatory charms provided via CMR.

        The app is in the saas rules, but no CMR in place, should report error
        """
        linter.lint_rules["saas"] = ["grafana"]
        error = linter.check_charms_ops_mandatory("grafana")

        assert error is not None
        assert error["id"] == "ops-charm-missing"
        assert error["charm"] == "grafana"

    def test_read_rules_plain_yaml(self, linter, tmp_path):
        """Test that a simple rules YAML is imported as expected."""
        rules_path = tmp_path / "rules.yaml"
        rules_path.write_text('---\nkey:\n "value"')

        linter.filename = str(rules_path)
        linter.read_rules()
        assert linter.lint_rules == {"key": "value"}

    def test_read_rules_include(self, linter, tmp_path):
        """Test that rules YAML with an include is imported as expected."""
        include_path = tmp_path / "include.yaml"
        include_path.write_text('key-inc:\n "value2"')

        rules_path = tmp_path / "rules.yaml"
        rules_path.write_text('---\n!include include.yaml\nkey:\n "value"')

        linter.filename = str(rules_path)
        linter.read_rules()
        assert linter.lint_rules == {"key": "value", "key-inc": "value2"}
