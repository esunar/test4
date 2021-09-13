#!/usr/bin/env python3

# This file is part of juju-lint, a tool for validating that Juju
# deloyments meet configurable site policies.
#
# Copyright 2018-2020 Canonical Limited.
# License granted by Canonical Limited.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Lint operations and rule processing engine."""
import collections
import json
import os.path
import pprint
import re

import yaml

from attr import attrs, attrib
import attr

from jujulint.util import flatten_list, is_container, extract_charm_name
from jujulint.logging import Logger

VALID_CONFIG_CHECKS = ("isset", "eq", "neq", "gte")

# Generic named tuple to represent the binary config operators (eq,neq,gte)
ConfigOperator = collections.namedtuple(
    "ConfigOperator", "name repr check error_template"
)

# TODO:
#  - missing relations for mandatory subordinates
#  - info mode, e.g. num of machines, version (e.g. look at ceph), architecture


def helper_operator_eq_check(check_value, actual_value):
    """Perform the actual equality check for the eq/neq rules."""
    match = False
    try:
        match = re.match(re.compile(str(check_value)), str(actual_value))
    except re.error:
        match = check_value == actual_value

    return match


@attrs
class ModelInfo(object):
    """Represent information obtained from juju status data."""

    charms = attrib(default=attr.Factory(set))
    app_to_charm = attrib(default=attr.Factory(dict))
    subs_on_machines = attrib(default=attr.Factory(dict))
    apps_on_machines = attrib(default=attr.Factory(dict))
    machines_to_az = attrib(default=attr.Factory(dict))

    # Output of our linting
    missing_subs = attrib(default=attr.Factory(dict))
    extraneous_subs = attrib(default=attr.Factory(dict))
    duelling_subs = attrib(default=attr.Factory(dict))
    az_unbalanced_apps = attrib(default=attr.Factory(dict))


class Linter:
    """Linter for a Juju model, instantiate a new class for each model."""

    def __init__(
        self,
        name,
        filename,
        controller_name="manual",
        model_name="manual",
        overrides=None,
        cloud_type=None,
        output_format="text",
    ):
        """Instantiate linter."""
        self.logger = Logger()
        self.lint_rules = {}
        self.model = ModelInfo()
        self.filename = filename
        self.overrides = overrides
        self.cloud_name = name
        self.cloud_type = cloud_type
        self.controller_name = controller_name
        self.model_name = model_name

        # output
        self.output_format = output_format
        self.output_collector = {
            "name": name,
            "controller": controller_name,
            "model": model_name,
            "rules": filename,
            "errors": [],
        }

        # collect errors only for non-text output (e.g. json)
        self.collect_errors = True if self.output_format != "text" else False

    def read_rules(self):
        """Read and parse rules from YAML, optionally processing provided overrides."""
        if os.path.isfile(self.filename):
            with open(self.filename, "r") as yaml_file:
                self.lint_rules = yaml.safe_load(yaml_file)
            if self.overrides:
                for override in self.overrides.split("#"):
                    (name, where) = override.split(":")
                    self.logger.info(
                        "[{}] [{}/{}] Overriding {} with {}".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            name,
                            where,
                        )
                    )
                    self.lint_rules["subordinates"][name] = dict(where=where)
            self.lint_rules["known charms"] = flatten_list(
                self.lint_rules["known charms"]
            )
            self.logger.debug(
                "[{}] [{}/{}] Lint Rules: {}".format(
                    self.cloud_name,
                    self.controller_name,
                    self.model_name,
                    pprint.pformat(self.lint_rules),
                )
            )
            return True
        self.logger.error("Rules file {} does not exist.".format(self.filename))
        return False

    def process_subordinates(self, app_d, app_name):
        """Iterate over subordinates and run subordinate checks."""
        # If this is a subordinate we have nothing else to do ATM
        if "units" not in app_d:
            return
        for unit in app_d["units"]:
            # juju_status = app_d["units"][unit]["juju-status"]
            # workload_status = app_d["units"][unit]["workload-status"]
            if "subordinates" in app_d["units"][unit]:
                subordinates = app_d["units"][unit]["subordinates"].keys()
                subordinates = [i.split("/")[0] for i in subordinates]
            else:
                subordinates = []
            self.logger.debug(
                "[{}] [{}/{}] {}: {}".format(
                    self.cloud_name,
                    self.controller_name,
                    self.model_name,
                    unit,
                    subordinates,
                )
            )
            machine = app_d["units"][unit]["machine"]
            self.model.subs_on_machines.setdefault(machine, set())
            for sub in subordinates:
                if sub in self.model.subs_on_machines[machine]:
                    self.model.duelling_subs.setdefault(sub, set())
                    self.model.duelling_subs[sub].add(machine)
                self.model.subs_on_machines[machine].add(sub)
            self.model.subs_on_machines[machine] = (
                set(subordinates) | self.model.subs_on_machines[machine]
            )
            self.model.apps_on_machines.setdefault(machine, set())
            self.model.apps_on_machines[machine].add(app_name)

        return

    def atoi(self, val):
        """Deal with complex number representations as strings, returning a number."""
        if type(val) != str:
            return val

        if type(val[-1]) != str:
            return val

        try:
            _int = int(val[0:-1])
        except Exception:
            return val

        quotient = 1024
        if val[-1].lower() == val[-1]:
            quotient = 1000

        conv = {"g": quotient ** 3, "m": quotient ** 2, "k": quotient}

        return _int * conv[val[-1].lower()]

    def isset(self, name, check_value, rule, config):
        """Check if value is set per rule constraints."""
        if rule in config:
            if check_value is True:
                self.logger.debug(
                    "[{}] [{}/{}] (PASS) Application {} correctly has config for '{}': {}.".format(
                        self.cloud_name,
                        self.controller_name,
                        self.model_name,
                        name,
                        rule,
                        config[rule],
                    )
                )
                return True
            actual_value = config[rule]
            self.handle_error(
                {
                    "id": "config-isset-check-false",
                    "tags": ["config", "isset"],
                    "description": "Checks for config condition 'isset'",
                    "application": name,
                    "rule": rule,
                    "actual_value": actual_value,
                    "message": "Application {} has config for {}: {}.".format(
                        name, rule, actual_value
                    ),
                }
            )
            return False
        elif check_value is False:
            self.logger.debug(
                "[{}] [{}/{}] (PASS) Application {} correctly had no config for '{}'.".format(
                    self.cloud_name,
                    self.controller_name,
                    self.model_name,
                    name,
                    rule,
                )
            )
            return True
        self.handle_error(
            {
                "id": "config-isset-check-true",
                "tags": ["config", "isset"],
                "description": "Checks for config condition 'isset' true",
                "application": name,
                "rule": rule,
                "message": "Application {} has no config for {}.".format(name, rule),
            }
        )
        return False

    def eq(self, app_name, check_value, config_key, app_config):
        """Check if value matches the provided value or regex, autodetecting regex."""
        operator = ConfigOperator(
            name="eq",
            repr="==",
            check=helper_operator_eq_check,
            error_template="Application {} has incorrect setting for '{}': Expected {}, got {}",
        )

        return self.check_config_generic(
            operator, app_name, check_value, config_key, app_config
        )

    def neq(self, app_name, check_value, config_key, app_config):
        """Check if value does not match a the config."""
        operator = ConfigOperator(
            name="neq",
            repr="!=",
            check=lambda check_value, actual_value: not helper_operator_eq_check(
                check_value, actual_value
            ),
            error_template="Application {} has incorrect setting for '{}': Should not be {}",
        )

        return self.check_config_generic(
            operator, app_name, check_value, config_key, app_config
        )

    def gte(self, app_name, check_value, config_key, app_config):
        """Check if value is greater than or equal to the check value."""

        def operator_gte_check(check_value, actual_value):
            """Perform the actual gte check."""
            current = self.atoi(actual_value)
            expected = self.atoi(check_value)
            return current >= expected

        operator = ConfigOperator(
            name="gte",
            repr=">=",
            check=operator_gte_check,
            error_template="Application {} has config for '{}' which is less than {}: {}",
        )

        return self.check_config_generic(
            operator, app_name, check_value, config_key, app_config
        )

    def check_config_generic(
        self, operator, app_name, check_value, config_key, app_config
    ):
        """Apply the provided config operator to the configuration."""
        model_header = "[{}] [{}/{}]".format(
            self.cloud_name,
            self.controller_name,
            self.model_name,
        )

        # First check if the config key is present
        if config_key not in app_config:
            self.logger.warn(
                "{} Application {} has no config for '{}', cannot determine if {} {}.".format(
                    model_header,
                    app_name,
                    config_key,
                    operator.repr,
                    repr(check_value),
                )
            )
            return False

        actual_value = app_config[config_key]

        # Apply the check callable and handle the possible cases
        if operator.check(check_value, actual_value):
            self.logger.debug(
                "{} Application {} has a valid config for '{}': {} ({} {})".format(
                    model_header,
                    app_name,
                    config_key,
                    repr(check_value),
                    operator.repr,
                    repr(actual_value),
                )
            )
            return True
        else:
            self.handle_error(
                {
                    "id": "config-{}-check".format(operator.name),
                    "tags": ["config", operator.name],
                    "description": "Checks for config condition '{}'".format(
                        operator.name
                    ),
                    "application": app_name,
                    "rule": config_key,
                    "expected_value": check_value,
                    "actual_value": actual_value,
                    "message": operator.error_template.format(
                        app_name,
                        config_key,
                        repr(check_value),
                        repr(actual_value),
                    ),
                }
            )
        return False

    def check_config(self, name, config, rules):
        """Check application against provided rules."""
        rules = dict(rules)
        for rule in rules:
            self.logger.debug(
                "[{}] [{}/{}] Checking {} for configuration {}".format(
                    self.cloud_name, self.controller_name, self.model_name, name, rule
                )
            )
            for check_op, check_value in rules[rule].items():
                # check_op should be the operator name, e.g. (eq, neq, gte, isset)
                if check_op in VALID_CONFIG_CHECKS:
                    check_method = getattr(self, check_op)
                    check_method(name, check_value, rule, config)
                else:
                    self.logger.warn(
                        "[{}] [{}/{}] Application {} has unknown check operation for {}: {}.".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            name,
                            rule,
                            check_op,
                        )
                    )

    def check_configuration(self, applications):
        """Check application configs in the model."""
        for application in applications.keys():
            # look for config rules for this application
            lint_rules = []
            if "charm" not in applications[application]:
                self.logger.warn(
                    "[{}] [{}/{}] Application {} has no charm.".format(
                        self.cloud_name,
                        self.controller_name,
                        self.model_name,
                        application,
                    )
                )
                continue

            charm_name = extract_charm_name(applications[application]["charm"])
            if "config" in self.lint_rules:
                if charm_name in self.lint_rules["config"]:
                    lint_rules = self.lint_rules["config"][charm_name].items()

            if self.cloud_type == "openstack":
                # process openstack config rules
                if "openstack config" in self.lint_rules:
                    if charm_name in self.lint_rules["openstack config"]:
                        lint_rules.extend(
                            self.lint_rules["openstack config"][charm_name].items()
                        )

            if lint_rules:
                if "options" in applications[application]:
                    self.check_config(
                        application,
                        applications[application]["options"],
                        lint_rules,
                    )

    def check_subs(self):
        """Check the subordinates in the model."""
        all_or_nothing = set()
        for machine in self.model.subs_on_machines:
            for sub in self.model.subs_on_machines[machine]:
                all_or_nothing.add(sub)

        for required_sub in self.lint_rules["subordinates"]:
            self.model.missing_subs.setdefault(required_sub, set())
            self.model.extraneous_subs.setdefault(required_sub, set())
            self.logger.debug(
                "[{}] [{}/{}] Checking for sub {}".format(
                    self.cloud_name, self.controller_name, self.model_name, required_sub
                )
            )
            where = self.lint_rules["subordinates"][required_sub]["where"]
            for machine in self.model.subs_on_machines:
                self.logger.debug(
                    "[{}] [{}/{}] Checking on {}".format(
                        self.cloud_name, self.controller_name, self.model_name, machine
                    )
                )
                present_subs = self.model.subs_on_machines[machine]
                apps = self.model.apps_on_machines[machine]
                if where.startswith("on "):  # only on specific apps
                    required_on = where[3:]
                    self.logger.debug(
                        "[{}] [{}/{}] Requirement {} is = from...".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            required_on,
                        )
                    )
                    if required_on not in apps:
                        self.logger.debug(
                            "[{}] [{}/{}] ... NOT matched".format(
                                self.cloud_name, self.controller_name, self.model_name
                            )
                        )
                        continue
                    self.logger.debug("[{}] [{}/{}] ... matched")
                # TODO this needs to be not just one app, but a list
                elif where.startswith("all except "):  # not next to this app
                    self.logger.debug(
                        "[{}] [{}/{}] requirement is != form...".format(
                            self.cloud_name, self.controller_name, self.model_name
                        )
                    )
                    not_on = where[11:]
                    if not_on in apps:
                        self.logger.debug(
                            "[{}] [{}/{}] ... matched, not wanted on this host".format(
                                self.cloud_name, self.controller_name, self.model_name
                            )
                        )
                        continue
                elif where == "host only":
                    self.logger.debug(
                        "[{}] [{}/{}] requirement is 'host only' form....".format(
                            self.cloud_name, self.controller_name, self.model_name
                        )
                    )
                    if is_container(machine):
                        self.logger.debug(
                            "[{}] [{}/{}] ... and we are a container, checking".format(
                                self.cloud_name, self.controller_name, self.model_name
                            )
                        )
                        # XXX check alternate names?
                        if required_sub in present_subs:
                            self.logger.debug(
                                "[{}] [{}/{}] ... found extraneous sub".format(
                                    self.cloud_name,
                                    self.controller_name,
                                    self.model_name,
                                )
                            )
                            for app in self.model.apps_on_machines[machine]:
                                self.model.extraneous_subs[required_sub].add(app)
                        continue
                    self.logger.debug(
                        "[{}] [{}/{}] ... and we are a host, will fallthrough".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                        )
                    )
                elif where == "all or nothing" and required_sub not in all_or_nothing:
                    self.logger.debug(
                        "[{}] [{}/{}] requirement is 'all or nothing' and was 'nothing'.".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                        )
                    )
                    continue
                # At this point we know we require the subordinate - we might just
                # need to change the name we expect to see it as
                elif where == "container aware":
                    self.logger.debug(
                        "[{}] [{}/{}] requirement is 'container aware'.".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                        )
                    )
                    if is_container(machine):
                        suffixes = self.lint_rules["subordinates"][required_sub][
                            "container-suffixes"
                        ]
                    else:
                        suffixes = self.lint_rules["subordinates"][required_sub][
                            "host-suffixes"
                        ]
                    self.logger.debug(
                        "[{}] [{}/{}] -> suffixes == {}".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            suffixes,
                        )
                    )
                    exceptions = []
                    if "exceptions" in self.lint_rules["subordinates"][required_sub]:
                        exceptions = self.lint_rules["subordinates"][required_sub][
                            "exceptions"
                        ]
                        self.logger.debug(
                            "[{}] [{}/{}] -> exceptions == {}".format(
                                self.cloud_name,
                                self.controller_name,
                                self.model_name,
                                exceptions,
                            )
                        )
                    found = False
                    for suffix in suffixes:
                        looking_for = "{}-{}".format(required_sub, suffix)
                        self.logger.debug(
                            "[{}] [{}/{}] -> Looking for {}".format(
                                self.cloud_name,
                                self.controller_name,
                                self.model_name,
                                looking_for,
                            )
                        )
                        if looking_for in present_subs:
                            self.logger.debug("-> FOUND!!!")
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            found = True
                    if not found:
                        for sub in present_subs:
                            if self.model.app_to_charm[sub] == required_sub:
                                self.logger.debug(
                                    "[{}] [{}/{}] Winner winner, chicken dinner! 🍗 {}".format(
                                        self.cloud_name,
                                        self.controller_name,
                                        self.model_name,
                                        sub,
                                    )
                                )
                                found = True
                    if not found:
                        for exception in exceptions:
                            if exception in apps:
                                self.logger.debug(
                                    "[{}] [{}/{}]-> continuing as found exception: {}".format(
                                        self.cloud_name,
                                        self.controller_name,
                                        self.model_name,
                                        exception,
                                    )
                                )
                                found = True
                    if not found:
                        self.logger.debug(
                            "[{}] [{}/{}] -> NOT FOUND".format(
                                self.cloud_name,
                                self.controller_name,
                                self.model_name,
                            )
                        )
                        for app in self.model.apps_on_machines[machine]:
                            self.model.missing_subs[required_sub].add(app)
                    self.logger.debug(
                        "[{}] [{}/{}] -> continue-ing back out...".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                        )
                    )
                    continue
                elif where not in ["all", "all or nothing"]:
                    self.logger.fubar(
                        "[{}] [{}/{}] Invalid requirement '{}' on {}".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            where,
                            required_sub,
                        )
                    )
                self.logger.debug(
                    "[{}] [{}/{}] requirement is 'all' OR we fell through.".format(
                        self.cloud_name,
                        self.controller_name,
                        self.model_name,
                    )
                )
                if required_sub not in present_subs:
                    for sub in present_subs:
                        if self.model.app_to_charm[sub] == required_sub:
                            self.logger.debug(
                                "Winner winner, chicken dinner! 🍗 {}".format(sub)
                            )
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            continue
                    self.logger.debug(
                        "[{}] [{}/{}] not found.".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                        )
                    )
                    for app in self.model.apps_on_machines[machine]:
                        self.model.missing_subs[required_sub].add(app)

        for sub in list(self.model.missing_subs.keys()):
            if not self.model.missing_subs[sub]:
                del self.model.missing_subs[sub]
        for sub in list(self.model.extraneous_subs.keys()):
            if not self.model.extraneous_subs[sub]:
                del self.model.extraneous_subs[sub]

    def check_charms(self):
        """Check we recognise the charms which are in the model."""
        for charm in self.model.charms:
            if charm not in self.lint_rules["known charms"]:
                self.handle_error(
                    {
                        "id": "unrecognised-charm",
                        "tags": ["charm", "unrecognised"],
                        "description": "An unrecognised charm is present in the model",
                        "charm": charm,
                        "message": "Charm '{}' not recognised".format(charm),
                    }
                )
        # Then look for charms we require
        for charm in self.lint_rules["operations mandatory"]:
            if charm not in self.model.charms:
                self.handle_error(
                    {
                        "id": "ops-charm-missing",
                        "tags": ["missing", "ops", "charm", "mandatory", "principal"],
                        "description": "An Ops charm is missing",
                        "charm": charm,
                        "message": "Ops charm '{}' is missing".format(charm),
                    }
                )
        if self.cloud_type == "openstack":
            for charm in self.lint_rules["openstack mandatory"]:
                if charm not in self.model.charms:
                    self.handle_error(
                        {
                            "id": "openstack-charm-missing",
                            "tags": [
                                "missing",
                                "openstack",
                                "charm",
                                "mandatory",
                                "principal",
                            ],
                            "description": "An Openstack charm is missing",
                            "charm": charm,
                            "message": "Openstack charm '{}' is missing".format(charm),
                        }
                    )
            for charm in self.lint_rules["operations openstack mandatory"]:
                if charm not in self.model.charms:
                    self.handle_error(
                        {
                            "id": "openstack-ops-charm-missing",
                            "tags": [
                                "missing",
                                "openstack",
                                "ops",
                                "charm",
                                "mandatory",
                                "principal",
                            ],
                            "description": "An Openstack ops charm is missing",
                            "charm": charm,
                            "message": "Openstack ops charm '{}' is missing".format(
                                charm
                            ),
                        }
                    )
        elif self.cloud_type == "kubernetes":
            for charm in self.lint_rules["kubernetes mandatory"]:
                if charm not in self.model.charms:
                    self.handle_error(
                        {
                            "id": "kubernetes-charm-missing",
                            "tags": [
                                "missing",
                                "kubernetes",
                                "charm",
                                "mandatory",
                                "principal",
                            ],
                            "description": "An Kubernetes charm is missing",
                            "charm": charm,
                            "message": "Kubernetes charm '{}' is missing".format(charm),
                        }
                    )
            for charm in self.lint_rules["operations kubernetes mandatory"]:
                if charm not in self.model.charms:
                    self.handle_error(
                        {
                            "id": "kubernetes-ops-charm-missing",
                            "tags": [
                                "missing",
                                "openstack",
                                "ops",
                                "charm",
                                "mandatory",
                                "principal",
                            ],
                            "description": "An Kubernetes ops charm is missing",
                            "charm": charm,
                            "message": "Kubernetes ops charm '{}' is missing".format(
                                charm
                            ),
                        }
                    )

    def results(self):
        """Provide results of the linting process."""
        if self.model.missing_subs:
            for sub in self.model.missing_subs:
                principals = ", ".join(sorted(self.model.missing_subs[sub]))
                self.handle_error(
                    {
                        "id": "ops-subordinate-missing",
                        "tags": ["missing", "ops", "charm", "mandatory", "subordinate"],
                        "description": "Checks for mandatory Ops subordinates",
                        "principals": principals,
                        "subordinate": sub,
                        "message": "Subordinate '{}' is missing for application(s): '{}'".format(
                            sub, principals
                        ),
                    }
                )

        if self.model.extraneous_subs:
            for sub in self.model.extraneous_subs:
                principals = ", ".join(sorted(self.model.extraneous_subs[sub]))
                self.handle_error(
                    {
                        "id": "subordinate-extraneous",
                        "tags": ["extraneous", "charm", "subordinate"],
                        "description": "Checks for extraneous subordinates in containers",
                        "principals": principals,
                        "subordinate": sub,
                        "message": "Application(s) '{}' has extraneous subordinate '{}'".format(
                            principals, sub
                        ),
                    }
                )
        if self.model.duelling_subs:
            for sub in self.model.duelling_subs:
                machines = ", ".join(sorted(self.model.duelling_subs[sub]))
                self.handle_error(
                    {
                        "id": "subordinate-duplicate",
                        "tags": ["duplicate", "charm", "subordinate"],
                        "description": "Checks for duplicate subordinates in a machine",
                        "machines": machines,
                        "subordinate": sub,
                        "message": "Subordinate '{}' is duplicated on machines: '{}'".format(
                            sub,
                            machines,
                        ),
                    }
                )
        if self.model.az_unbalanced_apps:
            for app in self.model.az_unbalanced_apps:
                (num_units, az_counter) = self.model.az_unbalanced_apps[app]
                az_map = ", ".join(
                    ["{}: {}".format(az, az_counter[az]) for az in sorted(az_counter)]
                )
                self.handle_error(
                    {
                        "id": "AZ-unbalance",
                        "tags": ["AZ"],
                        "description": "Checks for application balance across AZs",
                        "application": app,
                        "num_units": num_units,
                        "az_map": az_map,
                        "message": "Application '{}' is unbalanced across AZs: {} units, deployed as: {}".format(
                            app, num_units, az_map
                        ),
                    }
                )
        if self.output_format == "json":
            print(json.dumps(self.output_collector, indent=2, sort_keys=True))

    def map_charms(self, applications):
        """Process applications in the model, validating and normalising the names."""
        for app in applications:
            if "charm" in applications[app]:
                charm_name = extract_charm_name(applications[app]["charm"])
                self.model.charms.add(charm_name)
                self.model.app_to_charm[app] = charm_name
            else:
                self.handle_error(
                    {
                        "id": "charm-not-mapped",
                        "tags": ["charm", "mapped", "parsing"],
                        "description": "Detect the charm used by an application",
                        "application": app,
                        "message": "Could not detect which charm is used for application {}".format(
                            app
                        ),
                    }
                )

    def map_machines_to_az(self, machines):
        """Map machines in the model to their availability zone."""
        for machine in machines:
            if "hardware" not in machines[machine]:
                self.logger.warn(
                    "[{}] [{}/{}] Machine {} has no hardware info; skipping.".format(
                        self.cloud_name, self.controller_name, self.model_name, machine
                    )
                )
                continue

            hardware = machines[machine]["hardware"]
            found_az = False
            for entry in hardware.split():
                if entry.startswith("availability-zone="):
                    found_az = True
                    az = entry.split("=")[1]
                    self.model.machines_to_az[machine] = az
                    break
            if not found_az:
                self.logger.warn(
                    "[{}] [{}/{}] Machine {} has no availability-zone info in hardware field; skipping.".format(
                        self.cloud_name, self.controller_name, self.model_name, machine
                    )
                )

    def check_status(self, what, status, expected):
        """Lint the status of a unit."""
        current_status = status.get("current")
        if isinstance(expected, str):
            expected = [expected]
        if current_status not in expected:
            status_since = status.get("since")
            status_msg = status.get("message")
            self.handle_error(
                {
                    "id": "status-unexpected",
                    "tags": ["status"],
                    "description": "Checks for unexpected status in juju and workload",
                    "what": what,
                    "status_current": current_status,
                    "status_since": status_since,
                    "status_msg": status_msg,
                    "message": "{} has status '{}' (since: {}, message: {}); (We expected: {})".format(
                        what, current_status, status_since, status_msg, expected
                    ),
                }
            )

    def check_status_pair(self, name, status_type, data_d):
        """Cross reference satus of paired constructs, like machines and units."""
        if status_type in ["machine", "container"]:
            primary = "machine-status"
            primary_expected = "running"
            juju_expected = "started"
        elif status_type in ["unit", "subordinate"]:
            primary = "workload-status"
            primary_expected = ["active", "unknown"]
            juju_expected = "idle"
        elif status_type in ["application"]:
            primary = "application-status"
            primary_expected = ["active", "unknown"]
            juju_expected = None

        if primary in data_d:
            self.check_status(
                "{} {}".format(status_type.title(), name),
                data_d[primary],
                expected=primary_expected,
            )
            if juju_expected:
                if "juju-status" in data_d:
                    self.check_status(
                        "Juju on {} {}".format(status_type, name),
                        data_d["juju-status"],
                        expected=juju_expected,
                    )
                else:
                    self.logger.warn(
                        "[{}] [{}/{}] Could not determine Juju status for {}.".format(
                            self.cloud_name, self.controller_name, self.model_name, name
                        )
                    )
        else:
            self.logger.warn(
                "[{}] [{}/{}] Could not determine appropriate status key for {}.".format(
                    self.cloud_name,
                    self.controller_name,
                    self.model_name,
                    name,
                )
            )

    def check_statuses(self, juju_status, applications):
        """Check all statuses in juju status output."""
        for machine_name in juju_status["machines"]:
            self.check_status_pair(
                machine_name, "machine", juju_status["machines"][machine_name]
            )
            for container_name in juju_status["machines"][machine_name].get(
                "container", []
            ):
                self.check_status_pair(
                    container_name,
                    "container",
                    juju_status["machines"][machine_name][container_name],
                )

        for app_name in juju_status[applications]:
            self.check_status_pair(
                app_name, "application", juju_status[applications][app_name]
            )
            for unit_name in juju_status[applications][app_name].get("units", []):
                self.check_status_pair(
                    unit_name,
                    "unit",
                    juju_status[applications][app_name]["units"][unit_name],
                )

    # This is noisy and only covers a very theoretical corner case
    # where a misbehaving or malicious leader unit sets the
    # application-status to OK despite one or more units being in error
    # state.
    #
    # We could revisit this later by splitting it into two passes and
    # only warning about individual subordinate units if the
    # application-status for the subordinate claims to be OK.
    #
    # for subordinate_name in juju_status[applications][app_name]["units"][unit_name].get("subordinates", []):
    #     check_status_pair(subordinate_name, "subordinate",
    #                       juju_status[applications][app_name]["units"][unit_name]["subordinates"][subordinate_name])

    def check_azs(self, applications):
        """Lint AZ distribution."""
        azs = set()
        for machine in self.model.machines_to_az:
            azs.add(self.model.machines_to_az[machine])
        num_azs = len(azs)
        if num_azs != 3:
            self.handle_error(
                {
                    "id": "AZ-invalid-number",
                    "tags": ["AZ"],
                    "description": "Checks for a valid number or AZs (currently 3)",
                    "num_azs": num_azs,
                    "message": "Invalid number of AZs: '{}', expecting 3".format(
                        num_azs
                    ),
                }
            )
            return

        for app_name in applications:
            az_counter = collections.Counter()
            for az in azs:
                az_counter[az] = 0
            num_units = len(applications[app_name].get("units", []))
            if num_units <= 1:
                continue
            min_per_az = num_units // num_azs
            for unit in applications[app_name]["units"]:
                machine = applications[app_name]["units"][unit]["machine"]
                machine = machine.split("/")[0]
                if machine not in self.model.machines_to_az:
                    self.logger.error(
                        "[{}] [{}/{}] {}: Can't find machine {} in machine to AZ mapping data".format(
                            self.cloud_name,
                            self.controller_name,
                            self.model_name,
                            app_name,
                            machine,
                        )
                    )
                    continue
                az_counter[self.model.machines_to_az[machine]] += 1
            for az in az_counter:
                num_this_az = az_counter[az]
                if num_this_az < min_per_az:
                    self.model.az_unbalanced_apps[app_name] = [num_units, az_counter]

    def lint_yaml_string(self, yaml):
        """Lint provided YAML string."""
        parsed_yaml = yaml.safe_load(yaml)
        return self.do_lint(parsed_yaml)

    def lint_yaml_file(self, filename):
        """Load and lint provided YAML file."""
        if filename:
            with open(filename, "r") as infile:
                parsed_yaml = yaml.safe_load(infile.read())
                if parsed_yaml:
                    return self.do_lint(parsed_yaml)
        self.logger.fubar("Failed to parse YAML from file {}".format(filename))

    def do_lint(self, parsed_yaml):
        """Lint parsed YAML."""
        # Handle Juju 2 vs Juju 1
        applications = "applications"
        if applications not in parsed_yaml:
            applications = "services"

        if applications in parsed_yaml:

            # Build a list of deployed charms and mapping of charms <-> applications
            self.map_charms(parsed_yaml[applications])

            # Check configuration
            self.check_configuration(parsed_yaml[applications])

            # Then map out subordinates to applications
            for app in parsed_yaml[applications]:
                self.process_subordinates(parsed_yaml[applications][app], app)

            self.check_subs()
            self.check_charms()

            if "relations" not in parsed_yaml:
                self.map_machines_to_az(parsed_yaml["machines"])
                self.check_azs(parsed_yaml[applications])
                self.check_statuses(parsed_yaml, applications)
            else:
                self.logger.warn(
                    (
                        "[{}] [{}/{}] Relations data found; assuming a bundle and "
                        "skipping AZ and status checks."
                    ).format(
                        self.cloud_name,
                        self.model_name,
                        self.controller_name,
                    )
                )

            self.results()
        else:
            self.logger.warn(
                "[{}] [{}/{}] Model contains no applications, skipping.".format(
                    self.cloud_name,
                    self.controller_name,
                    self.model_name,
                )
            )

    def collect(self, error):
        """Collect an error and add it to the collector."""
        self.output_collector["errors"].append(error)

    def handle_error(self, error):
        """Collect an error and add it to the collector."""
        self.logger.error(
            "[{}] [{}/{}] {}.".format(
                self.cloud_name, self.controller_name, self.model_name, error["message"]
            )
        )
        if self.collect_errors:
            self.collect(error)
