= Juju Lint

== Introduction ==

This is intended to be run against a json dump of Juju status, which can be
generated as follows:

    juju status --format json > status.json

Then run `juju-lint` (using a rules file of `lint-rules.yaml`):

    ./juju-lint status.json

To use a different rules file:

    ./juju-lint -c my-rules.yaml status.json

== Rules File ==

For an example of a rules file, see `example-lint-rules.yaml`.

Supported top-level options for your rules file:

 1. `subordinates` - required subordinates.
 2. `known charms` - all primary charms should be in this list.
 3. `operations [mandatory|optional|subordinate]`
 4. `openstack [mandatory|optional|subordinate]`
