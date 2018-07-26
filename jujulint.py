#!/usr/bin/env python3

# Copyright (C) 2018 James Troup <james.troup@canonical.com>

import json
import logging
import optparse
import pprint
import sys

import yaml

from attr import attrs, attrib
import attr

# TODO:
#  - tests
#  - prometheus vs prometheus2
#  - non-OK statuses?
#  - missing relations for mandatory subordinates
#  - info mode, e.g. num of machines, version (e.g. look at ceph), architecture


@attrs
class ModelInfo(object):
    # Info obtained from juju status data
    charms = attrib(default=attr.Factory(set))
    app_to_charm = attrib(default=attr.Factory(dict))
    subs_on_machines = attrib(default=attr.Factory(dict))
    apps_on_machines = attrib(default=attr.Factory(dict))

    # Output of our linting
    missing_subs = attrib(default=attr.Factory(dict))
    extraneous_subs = attrib(default=attr.Factory(dict))
    duelling_subs = attrib(default=attr.Factory(dict))


def fubar(msg, exit_code=1):
    sys.stderr.write("E: %s\n" % (msg))
    sys.exit(exit_code)


def setup_logging(loglevel, logfile):
    logFormatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger()
    rootLogger.setLevel(loglevel)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    if logfile:
        try:
            fileLogger = logging.getLogger('file')
            # If we send output to the file logger specifically, don't propagate it
            # to the root logger as well to avoid duplicate output. So if we want
            # to only send logging output to the file, you would do this:
            #  logging.getLogger('file').info("message for logfile only")
            # rather than this:
            #  logging.info("message for console and logfile")
            fileLogger.propagate = False

            fileHandler = logging.FileHandler(logfile)
            fileHandler.setFormatter(logFormatter)
            rootLogger.addHandler(fileHandler)
            fileLogger.addHandler(fileHandler)
        except IOError:
            logging.error("Unable to write to logfile: {}".format(logfile))


def flatten_list(l):
    t = []
    for i in l:
        if not isinstance(i, list):
            t.append(i)
        else:
            t.extend(flatten_list(i))
    return t


def read_rules(options):
    with open(options.config, 'r') as yaml_file:
        lint_rules = yaml.safe_load(yaml_file)
    if options.override:
        for override in options.override.split("#"):
            (name, where) = override.split(":")
            logging.info("Overriding %s with %s" % (name, where))
            lint_rules["subordinates"][name] = dict(where=where)
    lint_rules["known charms"] = flatten_list(lint_rules["known charms"])
    logging.debug("Lint Rules: {}".format(pprint.pformat(lint_rules)))
    return lint_rules


def process_subordinates(app_d, app_name, model):
    # If this is a subordinate we have nothing else to do ATM
    if "units" not in app_d:
        return
    for unit in app_d["units"]:
        # juju_status = app_d["units"][unit]["juju-status"]
        # workload_status = app_d["units"][unit]["workload-status"]
        if "subordinates" in app_d["units"][unit]:
            subordinates = app_d["units"][unit]["subordinates"].keys()
            subordinates = [i.split("/")[0] for i in subordinates]
        else:
            subordinates = []
        logging.debug("%s: %s" % (unit, subordinates))
        machine = app_d["units"][unit]["machine"]
        model.subs_on_machines.setdefault(machine, set())
        for sub in subordinates:
            if sub in model.subs_on_machines[machine]:
                model.duelling_subs.setdefault(sub, set())
                model.duelling_subs[sub].add(machine)
        model.subs_on_machines[machine] = (set(subordinates) |
                                           model.subs_on_machines[machine])
        model.apps_on_machines.setdefault(machine, set())
        model.apps_on_machines[machine].add(app_name)

    return


def is_container(machine):
    if "/" in machine:
        return True
    else:
        return False


def check_subs(model, lint_rules):
    all_or_nothing = set()
    for machine in model.subs_on_machines:
        for sub in model.subs_on_machines[machine]:
            all_or_nothing.add(sub)

    for required_sub in lint_rules["subordinates"]:
        model.missing_subs.setdefault(required_sub, set())
        model.extraneous_subs.setdefault(required_sub, set())
        logging.debug("Checking for sub %s" % (required_sub))
        where = lint_rules["subordinates"][required_sub]["where"]
        for machine in model.subs_on_machines:
            logging.debug("Checking on %s" % (machine))
            present_subs = model.subs_on_machines[machine]
            if where.startswith("on "):  # only on specific machines
                logging.debug("requirement is = form...")
                required_on = where[3:]
                machine_name = machine.split("/")[0]
                if machine_name != required_on:
                    logging.debug("... NOT matched")
                    continue
                logging.debug("... matched")
            elif where == "host only":
                logging.debug("requirement is 'host only' form....")
                if is_container(machine):
                    logging.debug("... and we are a container, checking")
                    # XXX check alternate names?
                    if required_sub in present_subs:
                        logging.debug("... found extraneous sub")
                        for app in model.apps_on_machines[machine]:
                            model.extraneous_subs[required_sub].add(app)
                    continue
                logging.debug("... and we are a host, will fallthrough")
            elif (where == "all or nothing" and
                  required_sub not in all_or_nothing):
                logging.debug("requirement is 'all or nothing' and was 'nothing'.")
                continue
            # At this point we know we require the subordinate - we might just
            # need to change the name we expect to see it as
            elif where == "container aware":
                logging.debug("requirement is 'container aware'.")
                if is_container(machine):
                    suffixes = lint_rules["subordinates"][required_sub]["container-suffixes"]
                else:
                    suffixes = lint_rules["subordinates"][required_sub]["host-suffixes"]
                logging.debug("-> suffixes == %s" % (suffixes))
                found = False
                for suffix in suffixes:
                    looking_for = "%s-%s" % (required_sub, suffix)
                    logging.debug("-> Looking for %s" % (looking_for))
                    if looking_for in present_subs:
                        logging.debug("-> FOUND!!!")
                        found = True
                if not found:
                    for sub in present_subs:
                        if model.app_to_charm[sub] == required_sub:
                            logging.debug("!!: winner winner chicken dinner %s" % (sub))
                            found = True
                if not found:
                    logging.debug("-> NOT FOUND")
                    for app in model.apps_on_machines[machine]:
                        model.missing_subs[required_sub].add(app)
                logging.debug("-> continue-ing back out...")
                continue
            elif where not in ["all", "all or nothing"]:
                fubar("invalid requirement '%s' on %s" % (where, required_sub))
            logging.debug("requirement is 'all' OR we fell through.")
            if required_sub not in present_subs:
                for sub in present_subs:
                    if model.app_to_charm[sub] == required_sub:
                        logging.debug("!!!: winner winner chicken dinner %s" % (sub))
                        continue
                logging.debug("not found.")
                for app in model.apps_on_machines[machine]:
                    model.missing_subs[required_sub].add(app)

    for sub in list(model.missing_subs.keys())[:]:
        if not model.missing_subs[sub]:
            del model.missing_subs[sub]
    for sub in list(model.extraneous_subs.keys())[:]:
        if not model.extraneous_subs[sub]:
            del model.extraneous_subs[sub]


def check_charms(model, lint_rules):
    # Check we recognise the charms which are there
    for charm in model.charms:
        if charm not in lint_rules["known charms"]:
            logging.error("charm '%s' not recognised" % (charm))
    # Then look for charms we require
    for charm in lint_rules["operations mandatory"]:
        if charm not in model.charms:
            logging.error("ops charm '%s' not found" % (charm))
    for charm in lint_rules["openstack mandatory"]:
        if charm not in model.charms:
            logging.error("OpenStack charm '%s' not found" % (charm))


def results(model):
    if model.missing_subs:
        logging.info("The following subordinates couldn't be found:")
        for sub in model.missing_subs:
            logging.error(" -> %s [%s]" % (sub, ", ".join(sorted(model.missing_subs[sub]))))
    if model.extraneous_subs:
        logging.info("following subordinates where found unexpectedly:")
        for sub in model.extraneous_subs:
            logging.error(" -> %s [%s]" % (sub, ", ".join(sorted(model.extraneous_subs[sub]))))
    if model.duelling_subs:
        logging.info("following subordinates where found on machines more than once:")
        for sub in model.duelling_subs:
            logging.error(" -> %s [%s]" % (sub, ", ".join(sorted(model.duelling_subs[sub]))))


def map_charms(applications, model):
    for app in applications:
        # ### Charms
        # ##
        charm = applications[app]["charm"]
        # There are 4 forms:
        # - cs:~USER/SERIES/CHARM-REV
        # - cs:~USER/CHARM-REV
        # - cs:CHARM-REV
        # - local:SERIES/CHARM-REV
        if ":" in charm:
            charm = ":".join(charm.split(":")[1:])
        if "/" in charm:
            charm = charm.split("/")[-1]
        charm = "-".join(charm.split("-")[:-1])
        model.charms.add(charm)
        model.app_to_charm[app] = charm


def lint(filename, lint_rules):
    model = ModelInfo()

    with open(filename, 'r') as infile:
        j = json.loads(infile.read())

    # Handle Juju 2 vs Juju 1
    applications = "applications"
    if applications not in j:
        applications = "services"

    # Build a list of deployed charms and mapping of charms <-> applications
    map_charms(j[applications], model)

    # Then map out subordinates to applications
    for app in j[applications]:
        process_subordinates(j[applications][app], app, model)

    check_subs(model, lint_rules)
    check_charms(model, lint_rules)

    results(model)


def init():
    """Initalization, including parsing of options."""

    usage = """usage: %prog [OPTIONS]
    Sanity check a Juju model"""
    parser = optparse.OptionParser(usage)
    parser.add_option("-c", "--config", default="lint-rules.yaml",
                      help="File to read lint rules from. Defaults to `lint-rules.yaml`")
    parser.add_option("-o", "--override-subordinate",
                      dest="override",
                      help="override lint-rules.yaml, e.g. -o canonical-livepatch:all")
    parser.add_option("--loglevel", "-l", default='INFO',
                      help="Log level. Defaults to INFO")
    parser.add_option("--logfile", "-L", default=None,
                      help="File to log to in addition to stdout")
    (options, args) = parser.parse_args()

    return (options, args)


def main():
    (options, args) = init()
    setup_logging(options.loglevel, options.logfile)
    lint_rules = read_rules(options)
    for filename in args:
        lint(filename, lint_rules)


if __name__ == "__main__":
    main()
