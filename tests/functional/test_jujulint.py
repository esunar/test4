"""Functional tests for juju-lint."""
import json
import socket
from subprocess import check_call, check_output

import pytest


@pytest.mark.smoke
def test_juju_lint_startup():
    """Test starting juju-lint and print help string."""
    assert check_call("juju-lint --help".split()) == 0


@pytest.mark.smoke
def test_load_rules_file_from_path(rules_file, manual_file):
    """Test loading the rules file via command line argument."""
    assert check_call(f"juju-lint -c {rules_file} {manual_file}".split()) == 0


@pytest.mark.smoke
def test_load_default_rules_file(lint_rules_yaml, manual_file):
    """Test loading the default rules file."""
    assert check_call(f"juju-lint {manual_file}".split()) == 0


@pytest.mark.smoke
def test_json_output(rules_file, manual_file):
    """Test json output."""
    assert json.loads(
        check_output(
            f"juju-lint --format json -c {rules_file} {manual_file}".split()
        ).decode()
    )


@pytest.mark.cloud
async def test_audit_local_cloud(ops_test, local_cloud, rules_file):
    """Test running juju-lint against a live local cloud."""
    await ops_test.model.deploy("ubuntu")
    await ops_test.model.wait_for_idle()
    returncode, stdout, stderr = await ops_test.run(
        *f"juju-lint -c {rules_file}".split()
    )
    assert (
        f"[{local_cloud}] Linting model information for {socket.getfqdn()}, "
        f"controller {ops_test.controller_name}, model {ops_test.model_name}" in stderr
    )
    assert returncode == 0
