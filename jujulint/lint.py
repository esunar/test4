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
import pprint
import re

import yaml

from attr import attrs, attrib
import attr

from jujulint.util import flatten_list, is_container
from jujulint.logging import Logger

# TODO:
#  - tests
#  - non-OK statuses?
#  - missing relations for mandatory subordinates
#  - info mode, e.g. num of machines, version (e.g. look at ceph), architecture


class InvalidCharmNameError(Exception):
    """Represents an invalid charm name being processed."""

    pass


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

    def __init__(self):
        """Instantiate linter."""
        self.logger = Logger()
        self.lint_rules = {}
        self.model = ModelInfo()

    def read_rules(self, filename, overrides=None):
        """Read and parse rules from YAML, optionally processing provided overrides."""
        with open(filename, "r") as yaml_file:
            self.lint_rules = yaml.safe_load(yaml_file)
        if overrides:
            for override in overrides.split("#"):
                (name, where) = override.split(":")
                self.logger.info("Overriding %s with %s" % (name, where))
                self.lint_rules["subordinates"][name] = dict(where=where)
        self.lint_rules["known charms"] = flatten_list(self.lint_rules["known charms"])
        self.logger.debug("Lint Rules: {}".format(pprint.pformat(self.lint_rules)))

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
            self.logger.debug("%s: %s" % (unit, subordinates))
            machine = app_d["units"][unit]["machine"]
            self.model.subs_on_machines.setdefault(machine, set())
            for sub in subordinates:
                if sub in self.model.subs_on_machines[machine]:
                    self.model.duelling_subs.setdefault(sub, set())
                    self.model.duelling_subs[sub].add(machine)
            self.model.subs_on_machines[machine] = (
                set(subordinates) | self.model.subs_on_machines[machine]
            )
            self.model.apps_on_machines.setdefault(machine, set())
            self.model.apps_on_machines[machine].add(app_name)

        return

    def check_subs(self):
        """Check the subordinates in the model."""
        all_or_nothing = set()
        for machine in self.model.subs_on_machines:
            for sub in self.model.subs_on_machines[machine]:
                all_or_nothing.add(sub)

        for required_sub in self.lint_rules["subordinates"]:
            self.model.missing_subs.setdefault(required_sub, set())
            self.model.extraneous_subs.setdefault(required_sub, set())
            self.logger.debug("Checking for sub %s" % (required_sub))
            where = self.lint_rules["subordinates"][required_sub]["where"]
            for machine in self.model.subs_on_machines:
                self.logger.debug("Checking on %s" % (machine))
                present_subs = self.model.subs_on_machines[machine]
                apps = self.model.apps_on_machines[machine]
                if where.startswith("on "):  # only on specific apps
                    self.logger.debug("requirement is = form...")
                    required_on = where[3:]
                    if required_on not in apps:
                        self.logger.debug("... NOT matched")
                        continue
                    self.logger.debug("... matched")
                # TODO this needs to be not just one app, but a list
                elif where.startswith("all except "):  # not next to this app
                    self.logger.debug("requirement is != form...")
                    not_on = where[11:]
                    if not_on in apps:
                        self.logger.debug("... matched, not wanted on this host")
                        continue
                elif where == "host only":
                    self.logger.debug("requirement is 'host only' form....")
                    if is_container(machine):
                        self.logger.debug("... and we are a container, checking")
                        # XXX check alternate names?
                        if required_sub in present_subs:
                            self.logger.debug("... found extraneous sub")
                            for app in self.model.apps_on_machines[machine]:
                                self.model.extraneous_subs[required_sub].add(app)
                        continue
                    self.logger.debug("... and we are a host, will fallthrough")
                elif where == "all or nothing" and required_sub not in all_or_nothing:
                    self.logger.debug(
                        "requirement is 'all or nothing' and was 'nothing'."
                    )
                    continue
                # At this point we know we require the subordinate - we might just
                # need to change the name we expect to see it as
                elif where == "container aware":
                    self.logger.debug("requirement is 'container aware'.")
                    if is_container(machine):
                        suffixes = self.lint_rules["subordinates"][required_sub][
                            "container-suffixes"
                        ]
                    else:
                        suffixes = self.lint_rules["subordinates"][required_sub][
                            "host-suffixes"
                        ]
                    self.logger.debug("-> suffixes == %s" % (suffixes))
                    found = False
                    for suffix in suffixes:
                        looking_for = "%s-%s" % (required_sub, suffix)
                        self.logger.debug("-> Looking for %s" % (looking_for))
                        if looking_for in present_subs:
                            self.logger.debug("-> FOUND!!!")
                            found = True
                    if not found:
                        for sub in present_subs:
                            if self.model.app_to_charm[sub] == required_sub:
                                self.logger.debug(
                                    "!!: winner winner chicken dinner %s" % (sub)
                                )
                                found = True
                    if not found:
                        self.logger.debug("-> NOT FOUND")
                        for app in self.model.apps_on_machines[machine]:
                            self.model.missing_subs[required_sub].add(app)
                    self.logger.debug("-> continue-ing back out...")
                    continue
                elif where not in ["all", "all or nothing"]:
                    self.logger.fubar(
                        "invalid requirement '%s' on %s" % (where, required_sub)
                    )
                self.logger.debug("requirement is 'all' OR we fell through.")
                if required_sub not in present_subs:
                    for sub in present_subs:
                        if self.model.app_to_charm[sub] == required_sub:
                            self.logger.debug(
                                "!!!: winner winner chicken dinner %s" % (sub)
                            )
                            continue
                    self.logger.debug("not found.")
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
                self.logger.error("charm '%s' not recognised" % (charm))
        # Then look for charms we require
        for charm in self.lint_rules["operations mandatory"]:
            if charm not in self.model.charms:
                self.logger.error("ops charm '%s' not found" % (charm))
        for charm in self.lint_rules["openstack mandatory"]:
            if charm not in self.model.charms:
                self.logger.error("OpenStack charm '%s' not found" % (charm))

    def results(self):
        """Provide results of the linting process."""
        if self.model.missing_subs:
            self.logger.info("The following subordinates couldn't be found:")
            for sub in self.model.missing_subs:
                self.logger.error(
                    " -> %s [%s]"
                    % (sub, ", ".join(sorted(self.model.missing_subs[sub])))
                )
        if self.model.extraneous_subs:
            self.logger.info("following subordinates where found unexpectedly:")
            for sub in self.model.extraneous_subs:
                self.logger.error(
                    " -> %s [%s]"
                    % (sub, ", ".join(sorted(self.model.extraneous_subs[sub])))
                )
        if self.model.duelling_subs:
            self.logger.info(
                "following subordinates where found on machines more than once:"
            )
            for sub in self.model.duelling_subs:
                self.logger.error(
                    " -> %s [%s]"
                    % (sub, ", ".join(sorted(self.model.duelling_subs[sub])))
                )
        if self.model.az_unbalanced_apps:
            self.logger.error("The following apps are unbalanced across AZs: ")
            for app in self.model.az_unbalanced_apps:
                (num_units, az_counter) = self.model.az_unbalanced_apps[app]
                az_map = ", ".join(
                    ["%s: %s" % (az, az_counter[az]) for az in az_counter]
                )
                self.logger.error(
                    " -> %s: %s units, deployed as: %s" % (app, num_units, az_map)
                )

    def map_charms(self, applications):
        """Process applications in the model, validating and normalising the names."""
        for app in applications:
            charm = applications[app]["charm"]
            match = re.match(
                r"^(?:\w+:)?(?:~[\w-]+/)?(?:\w+/)?([a-zA-Z0-9-]+?)(?:-\d+)?$", charm
            )
            if not match:
                raise InvalidCharmNameError("charm name '{}' is invalid".format(charm))
            charm = match.group(1)
            self.model.charms.add(charm)
            self.model.app_to_charm[app] = charm

    def map_machines_to_az(self, machines, model):
        """Map machines in the model to their availability zone."""
        for machine in machines:
            if "hardware" not in machines[machine]:
                self.logger.error(
                    "I: Machine %s has no hardware info; skipping." % (machine)
                )
                continue

            hardware = machines[machine]["hardware"]
            found_az = False
            for entry in hardware.split():
                if entry.startswith("availability-zone="):
                    found_az = True
                    az = entry.split("=")[1]
                    model.machines_to_az[machine] = az
                    break
            if not found_az:
                self.logger.error(
                    "I: Machine %s has no availability-zone info in hardware field; skipping."
                    % (machine)
                )

    def check_status(self, what, status, expected):
        """Lint the status of a unit."""
        if isinstance(expected, str):
            expected = [expected]
        if status.get("current") not in expected:
            self.logger.error(
                "%s has status '%s' (since: %s, message: %s); {We expected: %s}"
                % (
                    what,
                    status.get("current"),
                    status.get("since"),
                    status.get("message"),
                    expected,
                )
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

        self.check_status(
            "%s %s" % (status_type.title(), name),
            data_d[primary],
            expected=primary_expected,
        )
        if juju_expected:
            self.check_status(
                "Juju on %s %s" % (status_type, name),
                data_d["juju-status"],
                expected=juju_expected,
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
            self.logger.error(
                "E: Found %s AZs (not 3); and I don't currently know how to lint that."
                % (num_azs)
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
                        "E: [%s] Can't find machine %s in machine to AZ mapping data"
                        % (app_name, machine)
                    )
                    continue
                az_counter[self.model.machines_to_az[machine]] += 1
            for az in az_counter:
                num_this_az = az_counter[az]
                if num_this_az < min_per_az:
                    self.model.az_unbalanced_apps[app_name] = [num_units, az_counter]

    def lint_string(self, yaml):
        """Lint provided YAML string."""
        parsed_yaml = yaml.safe_load(yaml)
        return self.do_lint(parsed_yaml)

    def lint_file(self, filename):
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

        # Build a list of deployed charms and mapping of charms <-> applications
        self.map_charms(parsed_yaml[applications], self.model)

        # Then map out subordinates to applications
        for app in parsed_yaml[applications]:
            self.process_subordinates(parsed_yaml[applications][app], app, self.model)

        self.map_machines_to_az(parsed_yaml["machines"], self.model)
        self.check_azs(parsed_yaml[applications], self.model)

        self.check_subs()
        self.check_charms()

        if parsed_yaml.get("machines"):
            self.check_statuses(parsed_yaml, applications)
        else:
            self.logger.info("Not checking status, this is a bundle")

        self.results()
