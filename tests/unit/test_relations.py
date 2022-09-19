#!/usr/bin/python3
"""Test the relations module."""
import pytest

from jujulint import relations

CHARM_TO_APP = {"nrpe-host", "nrpe-container"}
CHARM = "nrpe"
# rule to check all charms with nrpe-external-master endpoint.
RELATIONS = [["*:nrpe-external-master", "nrpe:nrpe-external-master"]]


@pytest.mark.parametrize(
    "correct_relation",
    [
        RELATIONS,
        [
            ["nrpe:nrpe-external-master", "*:nrpe-external-master"]
        ],  # inverting sequence doesn't change the endpoint
        [
            ["nrpe:nrpe-external-master", "keystone:nrpe-external-master"]
        ],  # able to find specific app relation
    ],
)
def test_relation_rule_valid(correct_relation, juju_status_relation):
    """Missing rules have empty set for endpoints with expected relations."""
    relation_rule = relations.RelationRule(
        charm_to_app=CHARM_TO_APP,
        applications=juju_status_relation,
        charm=CHARM,
        relations=correct_relation,
        not_exist=[[]],
        exception=set(),
    )
    relation_rule.check()
    assert relation_rule.missing_relations == {"nrpe:nrpe-external-master": list()}
    assert relation_rule.not_exist_error == list()
    assert relation_rule.__repr__() == "RelationRule(nrpe -> nrpe-external-master)"
    assert relation_rule.endpoint == "nrpe-external-master"


def test_relation_not_exist(juju_status_relation):
    """Ensure that finds a relation that shouldn't happen."""
    juju_status_relation["foo-charm"] = {
        "charm": "cs:foo-charm-7",
        "charm-name": "foo-charm",
        "relations": {
            "foo-endpoint": ["keystone"],
        },
        "endpoint-bindings": {
            "": "oam-space",
            "foo-endpoint": "oam-space",
        },
    }
    juju_status_relation["keystone"]["relations"]["foo-endpoint"] = ["foo-charm"]
    juju_status_relation["keystone"]["endpoint-bindings"]["foo-endpoint"] = "oam-space"
    relation_rule = relations.RelationRule(
        charm_to_app=CHARM_TO_APP,
        applications=juju_status_relation,
        charm=CHARM,
        relations=RELATIONS,
        not_exist=[["keystone:foo-endpoint", "foo-charm:foo-endpoint"]],
        exception=set(),
    )
    relation_rule.check()
    assert relation_rule.not_exist_error == [
        ["keystone:foo-endpoint", "foo-charm:foo-endpoint"]
    ]


def test_relation_not_exist_raise(juju_status_relation):
    """Test that raise exception when not_exist has wrong format."""
    juju_status_relation["foo-charm"] = {
        "charm": "cs:foo-charm-7",
        "charm-name": "foo-charm",
        "relations": {
            "bar-endpoint": ["keystone"],
        },
        "endpoint-bindings": {
            "": "oam-space",
            "bar-endpoint": "oam-space",
        },
    }

    with pytest.raises(relations.RelationError):
        relation_rule = relations.RelationRule(
            charm_to_app=CHARM_TO_APP,
            applications=juju_status_relation,
            charm=CHARM,
            relations=RELATIONS,
            not_exist=[["keystone", "foo-charm:foo-endpoint"]],
            exception=set(),
        )
        relation_rule.check()


@pytest.mark.parametrize(
    "expected_missing, exception",
    [
        ({"nrpe:nrpe-external-master": ["foo-charm"]}, set()),
        ({"nrpe:nrpe-external-master": list()}, {"foo-charm"}),
    ],
)
def test_missing_relation_and_exception(
    expected_missing, exception, juju_status_relation
):
    """Assert that exception is able to remove apps missing the relation."""
    # add a charm in apps that has the endpoint nrpe-external-master,
    # but it's not relating with nrpe.
    juju_status_relation["foo-charm"] = {
        "charm": "cs:foo-charm-7",
        "charm-name": "foo-charm",
        "relations": {
            "foo-endpoint": ["bar-charm"],
        },
        "endpoint-bindings": {
            "": "oam-space",
            "nrpe-external-master": "oam-space",
        },
    }
    relation_rule = relations.RelationRule(
        charm_to_app=CHARM_TO_APP,
        applications=juju_status_relation,
        charm=CHARM,
        relations=RELATIONS,
        not_exist=[[]],
        exception=exception,
    )
    relation_rule.check()
    assert relation_rule.missing_relations == expected_missing


def test_relation_rule_unknown_charm(mocker, juju_status_relation):
    """Empty relation for a unknown charm in rules and gives warning message."""
    charm = "foo_charm"
    warning_msg = (
        "Relations rules has an unexpected format. "
        f"It was not possible to find {charm} on rules"
    )
    logger_mock = mocker.patch.object(relations, "LOGGER")
    relation_rule = relations.RelationRule(
        charm_to_app=CHARM_TO_APP,
        applications=juju_status_relation,
        charm="foo_charm",
        relations=[["*:public", "keystone:public"]],
        not_exist=[[]],
        exception=set(),
    )
    assert relation_rule.relations == []
    logger_mock.warning.assert_has_calls([mocker.call(warning_msg)])


@pytest.mark.parametrize(
    "fake_relations, app_error, endpoint_error",
    [
        ([["foo:juju-info", "bar:juju-info"]], True, False),  # app doesn't exist
        ([["keystone:bar", "nrpe-host:foo"]], False, True),  # endpoint doesn't exist
    ],
)
def test_relation_rule_unknown_app_endpoint(
    fake_relations, app_error, endpoint_error, mocker, juju_status_relation
):
    """Ensure warning message and empty relations if app or endpoint is unknown."""
    logger_mock = mocker.patch.object(relations, "LOGGER")
    app, endpoint = fake_relations[0][0].split(":")
    if app_error:
        expected_msg = f"{app} not found on applications to check relations"
    elif endpoint_error:
        expected_msg = f"{app} don't have the endpoint: {endpoint} to check relations"

    relations_rule = relations.RelationRule(
        charm_to_app=CHARM_TO_APP,
        applications=juju_status_relation,
        charm=CHARM,
        relations=fake_relations,
        not_exist=[[]],
        exception=set(),
    )
    # assert that relations is empty
    assert relations_rule.relations == []
    logger_mock.warning.assert_has_calls([mocker.call(expected_msg)])


def test_relations_rules_bootstrap(juju_status_relation):
    """Test RelationsRulesBootStrap object."""
    charm_to_app = {"nrpe": {"nrpe-host", "nrpe-container"}}
    relations_rules = [
        {
            "charm": "nrpe",
            "check": [["*:nrpe-external-master", "nrpe:nrpe-external-master"]],
        },
        {
            "charm": "elasticsearch",
            "check": [
                ["elasticsearch:nrpe-external-master", "nrpe-host:nrpe-external-master"]
            ],
        },
    ]
    relations_rules = relations.RelationsRulesBootStrap(
        charm_to_app=charm_to_app,
        relations_rules=relations_rules,
        applications=juju_status_relation,
    ).check()
    assert len(relations_rules) == 2
    assert all(
        isinstance(relation_rule, relations.RelationRule)
        for relation_rule in relations_rules
    )
