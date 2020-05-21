= Juju Lint =

/!\ This is alpha software and backwards incompatible changes are expected.

== Introduction ==

This is intended to be run against a yaml dump of Juju status, a YAML dump of 
a juju bundle or a remote cloud or clouds via SSH.

To generate a status if you just want to audit placement:

    juju status --format yaml > status.yaml

For auditing configuration, you would want:

    juju export-bundle > bundle.yaml

Then run `juju-lint` (using a rules file of `lint-rules.yaml`):

    juju-lint -f status.yaml (or bundle.yaml)

You can also enable additional checks for specific cloud types by specifying
the cloud type with `-t` as such:

    juju-lint -f bundle.yaml -t openstack

For remote or mass audits, you can remote audit clouds via SSH.
To do this, you will need to add the clouds to your config file in:

    ~/.config/juju-lint/config.yaml

See the example config file in the `jujulint` directory of this repo.
This tool will use your existing SSH keys, SSH agent, and SSH config.
If you are running from the snap, you will need to connect the `ssh-keys`
interface in order to grant access to your SSH configuation.

To use a different rules file:

    ./juju-lint -c my-rules.yaml

For all other options, consult `juju-lint --help`

== Rules File ==

For an example of a rules file, see `example-lint-rules.yaml`.

Supported top-level options for your rules file:

 1. `subordinates` - required subordinates.
 2. `known charms` - all primary charms should be in this list.
 3. `operations [mandatory|optional|subordinate]`
 4. `openstack [mandatory|optional|subordinate]`
 5. `config` - application configuration auditing
 5. `[openstack|kubernetes] config` - config auditing for specific cloud types.

== License ==

Copyright 2020 Canonical Limited.
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
