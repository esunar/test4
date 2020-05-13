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
"""Cloud access module.

Runs locally or uses Fabric to parse a cloud's Juju bundle and provide SSH access to the units

Attributes:
     access_method (string, optional): Set the access method (local/ssh). Defaults to local.
     ssh_host (string, optional): Configuration to pass to Cloud module for accessing the cloud via SSH
     sudo_user (string, optional): User to switch to via sudo when accessing the cloud, passed to the Cloud module

Todo:
    * SSH to remote host honouring SSH config
    * Sudo to desired user
    * Get bundle from remote host
    * Parse bundle into dict
    * Add function to run command on a unit, via fabric and jump host if configured

"""
from fabric2 import Connection, Config
from jujulint.logging import Logger
from jujulint.lint import Linter
from subprocess import check_output
import socket
import yaml


class Cloud:
    """Cloud helper class."""

    def __init__(
        self,
        name,
        lint_rules=None,
        access_method="local",
        ssh_host=None,
        sudo_user=None,
        lint_overrides=None,
    ):
        """Instantiate Cloud configuration and state."""
        # instance variables
        self.cloud_state = {}
        self.access_method = "local"
        self.ssh_host = ""
        self.sudo_user = ""
        self.hostname = ""
        self.name = ""
        self.fabric_config = {}
        self.lint_rules = lint_rules
        self.lint_overrides = lint_overrides

        # process variables
        self.logger = Logger()
        self.logger.debug("Configuring {} cloud.".format(access_method))
        if sudo_user:
            self.sudo_user = sudo_user
            self.fabric_config = {"sudo": {"user": sudo_user}}
        if access_method == "ssh":
            if ssh_host:
                self.logger.debug("SSH host: {}".format(ssh_host))
                self.hostname = ssh_host
                self.connection = Connection(
                    ssh_host, config=Config(overrides=self.fabric_config)
                )
                self.access_method = "ssh"
        elif access_method == "local":
            self.hostname = socket.getfqdn()
        self.name = name

    def run_command(self, command):
        """Run a command via fabric on the local or remote host."""
        if self.access_method == "local":
            self.logger.debug("Running local command: {}".format(command))
            args = command.split(" ")
            return check_output(args)
        elif self.access_method == "ssh":
            if self.sudo_user:
                self.logger.debug(
                    "Running SSH command {} on {} as {}...".format(
                        command, self.hostname, self.sudo_user
                    )
                )
                result = self.connection.sudo(command, hide=True, warn=True)
                return result.stdout
            else:
                self.logger.debug(
                    "Running SSH command {} on {}...".format(command, self.hostname)
                )
                result = self.connection.run(command, hide=True, warn=True)
                return result.stdout

    def run_unit_command(self, target, command):
        """Run a command on a Juju unit and return the output."""

    def parse_yaml(self, yaml_string):
        """Parse YAML using PyYAML."""
        data = yaml.safe_load_all(yaml_string)
        return list(data)

    def get_juju_controllers(self):
        """Get a list of Juju controllers."""
        controller_output = self.run_command("juju controllers --format yaml")
        controllers = self.parse_yaml(controller_output)

        if len(controllers) > 0:
            self.logger.debug("Juju controller list: {}".format(controllers[0]))
            if "controllers" in controllers[0]:
                for controller in controllers[0]["controllers"].keys():
                    self.logger.info(
                        "[{}] Found Juju controller: {}".format(self.name, controller)
                    )
                    if controller not in self.cloud_state.keys():
                        self.cloud_state[controller] = {}
                    self.cloud_state[controller]["config"] = controllers[0][
                        "controllers"
                    ][controller]

    def get_juju_models(self):
        """Get a list of Juju models."""
        self.get_juju_controllers()
        for controller in self.cloud_state.keys():
            self.logger.info(
                "[{}] Getting models for controller: {}".format(self.name, controller)
            )
            models_data = self.run_command(
                "juju models -c {} --format yaml".format(controller)
            )
            self.logger.debug("Getting models from: {}".format(models_data))
            models = self.parse_yaml(models_data)
            if len(models) > 0:
                if "models" in models[0]:
                    for model in models[0]["models"]:
                        model_name = model["short-name"]
                        self.logger.info(
                            "[{}] Processing model {} for controller: {}".format(
                                self.name, model_name, controller
                            )
                        )
                        self.logger.debug(
                            "Processing model {} for controller {}: {}".format(
                                model_name, controller, model
                            )
                        )
                        if "models" not in self.cloud_state[controller].keys():
                            self.cloud_state[controller]["models"] = {}
                        if (
                            model_name
                            not in self.cloud_state[controller]["models"].keys()
                        ):
                            self.cloud_state[controller]["models"][model_name] = {}
                        self.cloud_state[controller]["models"][model_name][
                            "config"
                        ] = model

    def get_juju_status(self, controller, model):
        """Get a view of juju status for a given model."""
        status_data = self.run_command(
            "juju status -m {}:{} --format yaml".format(controller, model)
        )
        status = self.parse_yaml(status_data)
        self.logger.info(
            "[{}] Processing Juju status for model {} on controller {}".format(
                self.name, model, controller
            )
        )
        if len(status) > 0:
            if "model" in status[0].keys():
                self.cloud_state[controller]["models"][model]["version"] = status[0][
                    "model"
                ]["version"]
            if "machines" in status[0].keys():
                for machine in status[0]["machines"].keys():
                    machine_data = status[0]["machines"][machine]
                    self.logger.debug(
                        "Parsing status for machine {} in model {}: {}".format(
                            machine, model, machine_data
                        )
                    )
                    if "display-name" in machine_data:
                        machine_name = machine_data["display-name"]
                    else:
                        machine_name = machine
                    if "machines" not in self.cloud_state[controller]["models"][model]:
                        self.cloud_state[controller]["models"][model]["machines"] = {}
                    if (
                        "machine_name"
                        not in self.cloud_state[controller]["models"][model][
                            "machines"
                        ].keys()
                    ):
                        self.cloud_state[controller]["models"][model]["machines"][
                            machine_name
                        ] = {}
                    self.cloud_state[controller]["models"][model]["machines"][
                        machine_name
                    ].update(machine_data)
                    self.cloud_state[controller]["models"][model]["machines"][
                        machine_name
                    ]["machine_id"] = machine
            if "applications" in status[0].keys():
                for application in status[0]["applications"].keys():
                    application_data = status[0]["applications"][application]
                    self.logger.debug(
                        "Parsing status for application {} in model {}: {}".format(
                            application, model, application_data
                        )
                    )
                    if (
                        "applications"
                        not in self.cloud_state[controller]["models"][model]
                    ):
                        self.cloud_state[controller]["models"][model][
                            "applications"
                        ] = {}
                    if (
                        application
                        not in self.cloud_state[controller]["models"][model][
                            "applications"
                        ].keys()
                    ):
                        self.cloud_state[controller]["models"][model]["applications"][
                            application
                        ] = {}
                    self.cloud_state[controller]["models"][model]["applications"][
                        application
                    ].update(application_data)

    def get_juju_bundle(self, controller, model):
        """Get an export of the juju bundle for the provided model."""
        bundle_data = self.run_command(
            "juju export-bundle -m {}:{}".format(controller, model)
        )
        bundles = self.parse_yaml(bundle_data)
        self.logger.info(
            "[{}] Processing Juju bundle export for model {} on controller {}".format(
                self.name, model, controller
            )
        )
        self.logger.debug(
            "Juju bundle for model {} on controller {}: {}".format(
                model, controller, bundles
            )
        )
        if len(bundles) > 0:
            combined = {}
            for bundle in bundles:
                combined.update(bundle)
            if "applications" in combined:
                for application in combined["applications"].keys():
                    self.logger.debug(
                        "Parsing configuration for application {} in model {}: {}".format(
                            application, model, combined
                        )
                    )
                    application_config = combined["applications"][application]
                    if (
                        "applications"
                        not in self.cloud_state[controller]["models"][model]
                    ):
                        self.cloud_state[controller]["models"][model][
                            "applications"
                        ] = {}
                    if (
                        application
                        not in self.cloud_state[controller]["models"][model][
                            "applications"
                        ].keys()
                    ):
                        self.cloud_state[controller]["models"][model]["applications"][
                            application
                        ] = {}
                    self.cloud_state[controller]["models"][model]["applications"][
                        application
                    ].update(application_config)

    def get_juju_state(self):
        """Update our view of Juju-managed application state."""
        self.logger.info(
            "[{}] Getting Juju state for {}".format(self.name, self.hostname)
        )
        self.get_juju_models()
        self.logger.debug(
            "Cloud state for {} after gathering models:\n{}".format(
                self.name, yaml.dump(self.cloud_state)
            )
        )
        for controller in self.cloud_state.keys():
            for model in self.cloud_state[controller]["models"].keys():
                self.get_juju_status(controller, model)
                self.get_juju_bundle(controller, model)
        self.logger.debug(
            "Cloud state for {} after gathering apps:\n{}".format(
                self.name, yaml.dump(self.cloud_state)
            )
        )
        return self.cloud_state

    def refresh(self):
        """Refresh all information about the Juju cloud."""
        self.logger.info(
            "[{}] Refreshing cloud information for {}".format(self.name, self.hostname)
        )
        self.logger.debug("Running cloud-agnostic cloud refresh steps." "")
        state = self.get_juju_state()
        return state

    def audit(self):
        """Run cloud-type agnostic audit steps."""
        self.logger.info(
            "[{}] Auditing information for {}".format(self.name, self.hostname)
        )
        # run lint rules
        self.logger.debug("Running cloud-agnostic Juju audits.")
        if self.lint_rules:
            linter = Linter(self.name, self.lint_rules, overrides=self.lint_overrides)
            linter.read_rules()
            for controller in self.cloud_state.keys():
                for model in self.cloud_state[controller]["models"].keys():
                    self.logger.info(
                        "[{}] Linting model information for {}, controller {}, model {}...".format(
                            self.name, self.hostname, controller, model
                        )
                    )
                    linter.do_lint(self.cloud_state[controller]["models"][model])
