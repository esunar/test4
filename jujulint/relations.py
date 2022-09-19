#!/usr/bin/python3
"""Checks relations between applications."""
from logging import getLogger
from typing import Any, Dict, List, Set, Tuple

LOGGER = getLogger(__name__)


class RelationError(Exception):
    """Special exception for relations errors."""

    def __init__(self, msg: str):
        """Relation error message format.

        :param msg: Message of the exception found.
        :type msg: str
        """
        self.message = f"{self.__class__.__name__}: {msg}"


class RelationRule:
    """Object to check the relations rules."""

    def __init__(
        self,
        charm_to_app: Set,
        applications: Dict[str, Any],
        charm: str,
        relations: List[List[str]],
        not_exist: List[List[str]],
        exception: Set,
    ):
        """Relation Rule object.

        :param charm_to_app: A charm can have more than one application name
            e.g:(nrpe-host and nrpe-container). This parameters contains all
            applications name of a given charm.
        :type charm_to_app: Set
        :param applications: All applications of the file passed to lint.
        :type applications: Dict[str, Any]
        :param charm: Name of the charm to check the relations rules.
        :type charm: str
        :param relations: Relations that should be checked of a given charm
            having the following format:
            [[<application>:<application_endpoint>, <application>:<application_endpoint>]]
            If <application> == "*" it will check the relation using the endpoint
            on all applications form the file passed.
        :type relations: List[List[str]]
        :param not_exist: Relation that should not exist in the presence of the
            relations passed to be checked. This parameter has the following format:
            [[<application>:<application_endpoint>, <application>:<application_endpoint>]]
        :type not_exist: List[List[str]],
        :param exception: Set of applications that the rule doesn't apply to.
        :type exception: Set
        """
        self.charm_to_app = charm_to_app
        self.applications = applications
        self.charm = charm
        self.relations = relations
        self.not_exist = not_exist
        self.exception = exception
        # remove all possible app names from the subordinate app to not check itself
        self.apps_to_check = set(self.applications.keys()) - self.charm_to_app
        self.missing_relations = dict()
        self.not_exist_error = list()

    @property
    def relations(self) -> List[List[str]]:
        """Relations to be checked in a charm.

        :return: List of list containing the app and endpoint to check,
            with the following format: [[app_to_check, endpoint_to_check]]
        :rtype: List[List[str]]
        """
        return self._relations

    @relations.setter
    def relations(self, raw_relations_rules: List[List[str]]) -> None:
        """Relation setter of a rule.

        :param raw_relations_rules: Relations that should be checked of a given charm
            having the following format:
            [[<application_1>:<endpoint>], [<application_2>:<endpoint>]]
        :type raw_relations_rules: List[List[str]]
        :raises RelationError:  Raises RelationError if not in expected format.
        """
        self._relations = []
        if not all(raw_relations_rules):
            return
        for relation_rule in raw_relations_rules:
            try:
                app_0, endpoint_0 = self.check_app_endpoint_existence(relation_rule[0])
                app_1, endpoint_1 = self.check_app_endpoint_existence(relation_rule[1])
                if not all([app_0, endpoint_0, app_1, endpoint_1]):
                    # means that app or endpoint was not found
                    return
                if app_0 == self.charm:
                    self.endpoint = endpoint_0
                    app_to_check = app_1
                    endpoint_to_check = endpoint_1
                elif app_1 == self.charm:
                    self.endpoint = endpoint_1
                    app_to_check = app_0
                    endpoint_to_check = endpoint_0
                else:
                    msg = (
                        "Relations rules has an unexpected format. "
                        f"It was not possible to find {self.charm} on rules"
                    )
                    LOGGER.warning(msg)
                    return

                # check if all apps variations has the endpoint
                for app in self.charm_to_app:
                    self.check_app_endpoint_existence(f"{app}:{self.endpoint}")
                self._relations.append([app_to_check, endpoint_to_check])
            except (IndexError, ValueError) as e:
                raise RelationError(f"Relations rules has an unexpected format: {e}")

    def __repr__(self) -> str:
        """Representation of the RelationRule object.

        :return: representation.
        :rtype: str
        """
        return f"{self.__class__.__name__}({self.charm} -> {self.endpoint})"

    def check(self) -> None:
        """Apply the relations rules check."""
        self.relation_exist_check()
        self.relation_not_exist_check()

    def filter_by_app_and_endpoint(self, app: str, endpoint: str) -> Set:
        """Filter applications by the presence of an endpoint.

        :param app: Application to be filtered.
        :type app: str
        :param endpoint: Endpoint of a application.
        :type endpoint: str
        :return: Applications that matched with the endpoint passed.
        :rtype: Set
        """
        # NOTE(gabrielcocenza) this function just works with fields from juju status.
        # when app == "*", filters all apps that have the endpoint passed.
        if app == "*":
            return {
                app
                for app in self.apps_to_check
                if endpoint
                in self.applications.get(app, {}).get("endpoint-bindings", {})
            }
        return (
            set([app])
            if endpoint in self.applications.get(app, {}).get("endpoint-bindings", {})
            else set()
        )

    def filter_by_relation(self, apps: Set, endpoint: str) -> Set:
        """Filter applications that relate with an endpoint.

        :param apps: Applications to filter relations using the endpoint.
        :type apps: Set
        :param endpoint: endpoint of the applications.
        :type endpoint: str
        :return: Applications that has a relation with the apps using the endpoint.
        :rtype: Set
        """
        # NOTE(gabrielcocenza) this function just works with fields from juju status.
        apps_related = set()
        for app in apps:
            relations = self.applications.get(app, {}).get("relations", {})
            apps_related.update(relations.get(endpoint, []))
        return apps_related

    def relation_exist_check(self) -> None:
        """Check if app(s) are relating with an endpoint."""
        for relation in self.relations:
            app_to_check, endpoint_to_check = relation
            # applications in the bundle that have the endpoint to relate
            apps_with_endpoint_to_check = self.filter_by_app_and_endpoint(
                app_to_check,
                endpoint_to_check,
            )
            # applications that are relating using the endpoint from the relation rule
            apps_related_with_relation_rule = self.filter_by_relation(
                self.charm_to_app,
                self.endpoint,
            )
            self.missing_relations[f"{self.charm}:{self.endpoint}"] = sorted(
                list(
                    apps_with_endpoint_to_check
                    - apps_related_with_relation_rule
                    - self.exception
                )
            )

    def relation_not_exist_check(self) -> None:
        """Check if a relation happens when it shouldn't.

        :raises RelationError: raise RelationError if it has wrong format.
        """
        for relation in self.not_exist:
            if relation:
                app_endpoint_splitted = []
                try:
                    for app_endpoint in relation:
                        app, endpoint = self.check_app_endpoint_existence(app_endpoint)
                        app_endpoint_splitted.extend([app, endpoint])
                    (
                        app_to_check_0,
                        endpoint_to_check_0,
                        app_to_check_1,
                        _,
                    ) = app_endpoint_splitted
                    relations_app_endpoint_0 = self.filter_by_relation(
                        {app_to_check_0}, endpoint_to_check_0
                    )
                    if app_to_check_1 in relations_app_endpoint_0:
                        self.not_exist_error.append(relation)

                except (IndexError, ValueError) as e:
                    raise RelationError(f"Problem during check_relation_not_exist: {e}")

    def check_app_endpoint_existence(self, app_endpoint: str) -> Tuple[str, str]:
        """Check if app and endpoint exist on the object to lint.

        :param app_endpoint: app and endpoint separated by ":" with the following format:
            <application>:<application_endpoint>
        :type app_endpoint: str
        :return: application and endpoint
        :rtype: Tuple[str, str]
        """
        app, endpoint = app_endpoint.split(":")
        # app == "*" means all apps
        # a charm from relation rule can have different app names.
        if app != "*" and app != self.charm:
            if app not in self.applications.keys():
                LOGGER.warning(f"{app} not found on applications to check relations")
                return "", ""

            # juju-info is represented by "" on endpoint-bindings
            if endpoint != "juju-info" and endpoint not in self.applications[app].get(
                "endpoint-bindings", {}
            ):
                LOGGER.warning(
                    f"{app} don't have the endpoint: {endpoint} to check relations"
                )
                return "", ""
        return app, endpoint


class RelationsRulesBootStrap:
    """Bootstrap all relations rules to be checked."""

    def __init__(
        self,
        charm_to_app: Dict[str, Set],
        relations_rules: List[Dict[str, Any]],
        applications: Dict[str, Any],
    ):
        """Relations rules bootStrap object.

        :param charm_to_app: A charm can have more than one application name
            e.g:(nrpe-host and nrpe-container). This parameters contains all
            applications name of a given charm.
        :type charm_to_app: Dict[str, Set]
        :param relations_rules: Relations rules from the rule file.
        :type relations_rules: List[Dict[str, Any]]
        :param applications: All applications of the file passed to lint.
        :type applications: Dict[str, Any]
        """
        self.charm_to_app = charm_to_app
        self.relations_rules = relations_rules
        self.applications = applications

    def check(self) -> List[RelationRule]:
        """Check all RelationRule objects.

        :return: List containing all RelationRule objects.
        :rtype: List[RelationRule]
        """
        relations_rules = [
            RelationRule(
                charm_to_app=self.charm_to_app.get(rule.get("charm", ""), set()),
                applications=self.applications,
                charm=rule.get("charm"),
                relations=rule.get("check", [[]]),
                not_exist=rule.get("not-exist", [[]]),
                exception=set(rule.get("exception", set())),
            )
            for rule in self.relations_rules
        ]

        for rule in relations_rules:
            rule.check()
        return relations_rules
