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
"""Logging helper functions."""
import logging
import sys


class Logger:
    """Helper class for logging."""

    def __init__(self, level=None, logfile=None):
        """Set up logging instance and set log level."""
        self.logger = logging.getLogger()
        self.set_level(level)
        if not len(self.logger.handlers):
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self.logger.addHandler(console)
            if logfile:
                try:
                    file_logger = logging.getLogger("file")
                    # If we send output to the file logger specifically, don't propagate it
                    # to the root logger as well to avoid duplicate output. So if we want
                    # to only send logging output to the file, you would do this:
                    #  logging.getLogger('file').info("message for logfile only")
                    # rather than this:
                    #  logging.info("message for console and logfile")
                    file_logger.propagate = False

                    file_handler = logging.file_handler(logfile)
                    file_handler.setFormatter(formatter)
                    self.logger.addHandler(file_handler)
                    file_logger.addHandler(file_handler)
                except IOError:
                    logging.error("Unable to write to logfile: {}".format(logfile))

    def fubar(self, msg, exit_code=1):
        """Exit and print to stderr because everything is FUBAR."""
        sys.stderr.write("E: %s\n" % (msg))
        sys.exit(exit_code)

    def set_level(self, level="info"):
        """Set the level to the provided level."""
        if level:
            level = level.lower()
        else:
            return False

        if level == "debug":
            logging.basicConfig(level=logging.DEBUG)
        elif level == "warn":
            self.logger.setLevel(logging.WARN)
        elif level == "error":
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.setLevel(logging.INFO)
        return True

    def debug(self, message):
        """Log a message with debug loglevel."""
        self.logger.debug(message)

    def warn(self, message):
        """Log a message with warn loglevel."""
        self.logger.warn(message)

    def info(self, message):
        """Log a message with info loglevel."""
        self.logger.info(message)

    def error(self, message):
        """Log a message with warn loglevel."""
        self.logger.error(message)
