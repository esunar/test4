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
"""Config handling routines."""

from argparse import ArgumentParser

from confuse import Configuration


class Config(Configuration):
    """Helper class for holding parsed config, extending confuse's BaseConfiguraion class."""

    def __init__(self):
        """Wrap the initialisation of confuse's Configuration object providing defaults for our application."""
        super().__init__("juju-lint", __name__)

        self.parser = ArgumentParser(description="Sanity check one or more Juju models")
        self.parser.add_argument(
            "-l",
            "--log-level",
            type=str,
            default="info",
            nargs="?",
            help="The default log level, valid options are info, warn, error or debug",
            dest="logging.loglevel",
        )
        self.parser.add_argument(
            "-d",
            "--output-dir",
            type=str,
            default="output",
            nargs="?",
            help="The folder to use when saving gathered cloud data and lint reports.",
            dest="output.folder",
        )
        self.parser.add_argument(
            "--dump-state",
            type=str,
            help=(
                "Optionally, dump cloud state as YAML into --output-dir."
                "Use with caution, as dumps will contain sensitve data."
            ),
            dest="output.dump",
        )
        self.parser.add_argument(
            "-c",
            "--config",
            default="lint-rules.yaml",
            help="File to read lint rules from. Defaults to `lint-rules.yaml`",
            dest="rules.file",
        )
        self.parser.add_argument(
            "manual-file",
            metavar="manual-file",
            nargs="?",
            type=str,
            default=None,
            help=(
                "File to read state from. Supports bundles and status output in YAML format."
                "Setting this disables collection of data from remote or local clouds configured via config.yaml."
            ),
        )
        self.parser.add_argument(
            "-t",
            "--cloud-type",
            help=(
                "Sets the cloud type when specifying a YAML file to audit with -f or --cloud-file."
            ),
            dest="manual-type",
        )
        self.parser.add_argument(
            "-o",
            "--override-subordinate",
            dest="override.subordinate",
            help="override lint-rules.yaml, e.g. -o canonical-livepatch:all",
        )
        self.parser.add_argument(
            "--logfile",
            "-L",
            default=None,
            help="File to log to in addition to stdout",
            dest="logging.file",
        )
        self.parser.add_argument(
            "--format",
            "-F",
            choices=["text", "json"],
            default="text",
            help="Format for output",
        )

        args = self.parser.parse_args()
        self.set_args(args, dots=True)
