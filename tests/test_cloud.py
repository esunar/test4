#!/usr/bin/python3
"""Tests for Cloud."""
from subprocess import CalledProcessError
from unittest.mock import call, patch


class TestCloud:
    """Test the main Cloud class."""

    @patch("jujulint.cloud.check_output")
    def test_get_bundle_no_apps(self, mock_check_out, cloud):
        """Models with no apps raises CalledProcessError to export bundle."""
        cmd = ["juju", "export-bundle", "-m", "my_controller:controller"]
        e = CalledProcessError(1, cmd)
        mock_check_out.side_effect = e
        cloud.get_juju_bundle("my_controller", "controller")
        expected_error_msg = call.error(e)

        expected_warn_msg = call.warn(
            (
                "An error happened to get the bundle on my_controller:controller. "
                "If the model doesn't have apps, disconsider this message."
            )
        )
        assert expected_error_msg in cloud.logger.method_calls
        assert expected_warn_msg in cloud.logger.method_calls

    @patch("jujulint.cloud.Cloud.parse_yaml")
    @patch("jujulint.cloud.Cloud.run_command")
    def test_get_bundle_offer_side(
        self, mock_run, mock_parse, cloud, juju_export_bundle
    ):
        """Test the bundle generated in the offer side."""
        # simulate cloud_state with info that came from "get_juju_status"
        cloud.cloud_state = {
            "my_controller": {
                "models": {
                    "my_model_1": {
                        "applications": {
                            "nrpe": {
                                "charm-origin": "charmhub",
                                "os": "ubuntu",
                                "endpoint-bindings": {"": "alpha", "monitors": "alpha"},
                            }
                        }
                    },
                    "my_model_2": {},
                }
            }
        }
        mock_parse.return_value = juju_export_bundle["my_model_1"]
        # "offers" field exists inside nrpe because of the overlay bundle.
        # saas field doesn't exist in the offer side because there is no url.
        # don't overwrite information that came from "get_juju_status".
        expected_cloud_state = {
            "my_controller": {
                "models": {
                    "my_model_1": {
                        "applications": {
                            "nrpe": {
                                "charm": "nrpe",
                                "charm-origin": "charmhub",
                                "os": "ubuntu",
                                "endpoint-bindings": {"": "alpha", "monitors": "alpha"},
                                "channel": "stable",
                                "revision": 86,
                                "offers": {
                                    "nrpe": {
                                        "endpoints": ["monitors"],
                                        "acl": {"admin": "admin"},
                                    }
                                },
                            },
                            "ubuntu": {
                                "charm": "ubuntu",
                                "channel": "stable",
                                "revision": 19,
                                "num_units": 1,
                                "to": ["0"],
                                "constraints": "arch=amd64",
                            },
                        }
                    },
                    "my_model_2": {},
                }
            }
        }
        cloud.get_juju_bundle("my_controller", "my_model_1")
        assert mock_run.called_once_with(
            "juju export-bundle -m my_controller:my_model_1"
        )
        assert cloud.cloud_state == expected_cloud_state

    @patch("jujulint.cloud.Cloud.parse_yaml")
    @patch("jujulint.cloud.Cloud.run_command")
    def test_get_bundle_consumer_side(
        self, mock_run, mock_parse, cloud, juju_export_bundle
    ):
        """Test the bundle generated in the consumer side."""
        mock_parse.return_value = juju_export_bundle["my_model_2"]
        # "offers" field won't exist in the consumer side
        # saas field exists because the consumer side shows url
        expected_cloud_state = {
            "my_controller": {
                "models": {
                    "my_model_1": {},
                    "my_model_2": {
                        "applications": {
                            "nagios": {
                                "charm": "nagios",
                                "channel": "stable",
                                "revision": 49,
                                "num_units": 1,
                                "to": ["0"],
                                "constraints": "arch=amd64",
                            }
                        },
                        "saas": {
                            "nrpe": {"url": "my_controller:admin/my_model_1.nrpe"}
                        },
                    },
                }
            }
        }
        cloud.get_juju_bundle("my_controller", "my_model_2")
        assert mock_run.called_once_with(
            "juju export-bundle -m my_controller:my_model_2"
        )
        assert cloud.cloud_state == expected_cloud_state
