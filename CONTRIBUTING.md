# Contributing

## Overview

This documents explains the processes and practices recommended for contributing enhancements to
this project.

- Generally, before developing enhancements to this project, you should consider [report a bug
  ](https://bugs.launchpad.net/juju-lint) explaining your use case.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - documentation
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto
  the `master` branch. This also avoids merge commits and creates a linear Git commit history.

### Developing

Clone this repository:
```shell
git clone git+ssh://<LAUNCHPAD_USER>@git.launchpad.net/juju-lint
cd juju-lint/
```

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

After making your changes you can run the CI without the need of building and installing the snap by using:

```shell
python3 -m jujulint.cli <PATH_TO_YAML> -c <PATH_TO_RULE_FILE> -l debug
```


### Testing

```shell
make lint            # check code style
make test            # unit tests
make build           # build the snap
make clean           # clean the snapcraft lxd containers
```

## Canonical Contributor Agreement

Canonical welcomes contributions to the juju-lint. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.
