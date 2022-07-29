# Release Notes

The recommended way to pick up the latest snap release is via the latest/edge channel:

```
$ snap install juju-lint --channel=latest/edge
```

# 1.0.3 (July 2022)

## Summary of the changes

- ceph-mon config checks for slow requests
- juju-lint automatically include cloud_type if not passed in the cli
- added new rule files matching the clouds used on fce-templates
- added new regex operator for checking charms configurations
- warnings if bundle does not specify explicit bindings
- changed snap base from core18(python3.6) to core20(python3.8)

## Bug Fixes

- [expose monitoring threshold/severity for "slow requests"](https://bugs.launchpad.net/juju-lint/+bug/1922602)
- [juju-lint fails to parse default bundle from SolQA/FE](https://bugs.launchpad.net/juju-lint/+bug/1972158)
- [juju-lint crashes on models without applications when collecting bundles](https://bugs.launchpad.net/juju-lint/+bug/1929625)
- [juju-lint should automatically include cloud_type](https://bugs.launchpad.net/juju-lint/+bug/1980019)
- [charm 'ceph-dashboard' and 'openstack-loadbalancer' not recognised](https://bugs.launchpad.net/juju-lint/+bug/1965243)
- [charm 'bootstack-charmers-homer-dashboard' not recognised](https://bugs.launchpad.net/juju-lint/+bug/1965244)
- [default queue length checks for rabbitmq on openstack clouds is far too small](https://bugs.launchpad.net/juju-lint/+bug/1939748)
- [getting many KeyError errors during spaces checks](https://bugs.launchpad.net/juju-lint/+bug/1979382)
- [juju-lint doesn't build the snap with local repository](https://bugs.launchpad.net/juju-lint/+bug/1979696)

# 1.0.2 (June 2022)

## Summary of the changes
- added black and isort to the project
- added CONTRIBUTING.md guide to the project
- fixed broken k8s rules
- added space checks
- check if percona cluster tunning-level is set to "fast"
- updated README documentation by adding full examples
- added local-users as an optional subordinate operations charm
- added build and clean options to makefile
- added a "suffix" option for config checks
- added the "allow-multiple" condition for subordinates
- added the "metal only" condition for subordinates
- added support for includes, as well as several reference rules yaml files
- added support for CMR applications (SAAS)
- added missing charms to the rules
- ignore "executing" units in the unit status check for 1hr
- added 'neq' check for charm configuration
- added operations/kubernetes mandatory charms and optional charms for k8s
- added json output format
- warn on unconfigured lacp_bonds and netlinks options
- warn if unattended upgrades are enabled
- ensure the ovn db election timeout is ≥ 4

## Bug Fixes
- [snap release 52 is broken on bionic](https://bugs.launchpad.net/juju-lint/+bug/1979349)
- [alert on lack of explicit default bindings](https://bugs.launchpad.net/juju-lint/+bug/1851485)
- [change python version](https://bugs.launchpad.net/juju-lint/+bug/1977469)
- [add additional import for k8s dependencies](https://bugs.launchpad.net/juju-lint/+bug/1967325)
- [add rule for percona-cluster tuning-level](https://bugs.launchpad.net/juju-lint/+bug/1930892)
- [check for known relations requiring binding to the same space](https://bugs.launchpad.net/juju-lint/+bug/1840814)
- [update README to remove non-existent -f flag](https://bugs.launchpad.net/juju-lint/+bug/1939437)
- [update README to mention exporting defaults](https://bugs.launchpad.net/juju-lint/+bug/1958899)
- [juju-lint fails on exported bundle with overlay section](https://bugs.launchpad.net/juju-lint/+bug/1915934)
- [parsing for charm name does not properly handle charm hub sources](https://bugs.launchpad.net/juju-lint/+bug/1950980)
- [add targeting options to config checks (similar to subordinate rules)](https://bugs.launchpad.net/juju-lint/+bug/1944406)
- [juju lint-false positives for double nrpe](https://bugs.launchpad.net/juju-lint/+bug/1855858)
- [juju lint expecting hw-health on VM](https://bugs.launchpad.net/juju-lint/+bug/1903973)
- [ovn should be checked in addition to neutron-openvswitch](https://bugs.launchpad.net/juju-lint/+bug/1939434)
- [support multiple rulesets](https://bugs.launchpad.net/juju-lint/+bug/1916045)
- [juju-lint does not recognize mysql-router and mysql-innodb-cluster charms](https://bugs.launchpad.net/juju-lint/+bug/1904038)
- [juju-lint canonical-rules.yaml needs updating for focal-ussuri](https://bugs.launchpad.net/juju-lint/+bug/1896551)
- [juju-lint throws a false positive about the missing LMA if the LMA is deployed in the separate model](https://bugs.launchpad.net/juju-lint/+bug/1897262)
- [add "status age" configuration for unexpected status check](https://bugs.launchpad.net/juju-lint/+bug/1942998)
- [juju-lint should differentiate between config that comes from the user / default values](https://bugs.launchpad.net/juju-lint/+bug/1943222)
- [juju-lint does not support Kubernetes deployment](https://bugs.launchpad.net/juju-lint/+bug/1805875)
- [juju-lint does not verify deployment of kubernetes-service-checks](https://bugs.launchpad.net/juju-lint/+bug/1940546)
- [juju-lint fails if charmstore namespace contains '.'](https://bugs.launchpad.net/juju-lint/+bug/1934197)
- [juju-lint giving false positives about ntp option auto_peers](https://bugs.launchpad.net/juju-lint/+bug/1905609)
- [warn on unconfigured lacp_bonds and netlinks options](https://bugs.launchpad.net/juju-lint/+bug/1912344)
- [check for reasonable value of ovn db election timeout](https://bugs.launchpad.net/juju-lint/+bug/1904222)
- [incorrect logrotated charm name in canonical-rules.yaml](https://bugs.launchpad.net/juju-lint/+bug/1913405)
- [juju-lint giving false positives about live-migration setting for nova-compute](https://bugs.launchpad.net/juju-lint/+bug/1905608)
- [add rule alerting about unattended upgrades](https://bugs.launchpad.net/juju-lint/+bug/1903720)
- [juju lint-false positives for nagios](https://bugs.launchpad.net/juju-lint/+bug/1855857)
