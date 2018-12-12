= Juju Lint =

/!\ This is alpha software and backwards incompatible changes are expected.

== Introduction ==

This is intended to be run against a yaml dump of Juju status, which can be
generated as follows:

    juju status --format yaml > status.yaml

Then run `juju-lint` (using a rules file of `lint-rules.yaml`):

    ./juju-lint status.yaml

To use a different rules file:

    ./juju-lint -c my-rules.yaml status.yaml

== Rules File ==

For an example of a rules file, see `example-lint-rules.yaml`.

Supported top-level options for your rules file:

 1. `subordinates` - required subordinates.
 2. `known charms` - all primary charms should be in this list.
 3. `operations [mandatory|optional|subordinate]`
 4. `openstack [mandatory|optional|subordinate]`

== License ==

Copyright 2018 Canonical Limited.
License granted by Canonical Limited.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3, as
published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranties of
MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
