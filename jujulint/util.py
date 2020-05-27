#! /usr/bin/env python3
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
"""Utility library for all helpful functions this project uses."""


def flatten_list(lumpy_list):
    """Flatten a list potentially containing other lists."""
    flat_list = []
    for item in lumpy_list:
        if not isinstance(item, list):
            flat_list.append(item)
        else:
            flat_list.extend(flatten_list(item))
    return flat_list


def is_container(machine):
    """Check if a provided machine is a container."""
    if "/" in machine:
        return True
    else:
        return False
