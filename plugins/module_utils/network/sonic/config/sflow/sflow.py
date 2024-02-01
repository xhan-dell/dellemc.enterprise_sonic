#
# -*- coding: utf-8 -*-
# Copyright 2023 Dell Inc. or its subsidiaries. All Rights Reserved
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The sonic_sflow class
It is in this file where the current configuration (as dict)
is compared to the provided configuration (as dict) and the command set
necessary to bring the current configuration to it's desired end-state is
created
"""
from __future__ import absolute_import, division, print_function
__metaclass__ = type

from copy import deepcopy

from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.cfg.base import (
    ConfigBase,
)
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import (
    to_list,
    validate_config
)
from ansible_collections.dellemc.enterprise_sonic.plugins.module_utils.network.sonic.facts.facts import Facts

from ansible_collections.dellemc.enterprise_sonic.plugins.module_utils.network.sonic.utils.utils \
    import (
        get_diff,
        update_states,
        to_request,
        edit_config,
        get_normalize_interface_name
    )


class Sflow(ConfigBase):
    """
    The sonic_sflow class
    """

    gather_subset = [
        '!all',
        '!min',
    ]

    gather_network_resources = [
        'sflow',
    ]

    sflow_uri = "data/openconfig-sampling-sflow:sampling/sflow"

    sflow_diff_test_keys = [{"collectors": {"port": "", "address": "", "network_instance": ""}},
                            {"interfaces": {"name": ""}}]

    def __init__(self, module):
        super(Sflow, self).__init__(module)

    def get_sflow_facts(self):
        """ Get the 'facts' (the current configuration)

        :rtype: A dictionary
        :returns: The current configuration as a dictionary
        """
        facts, _warnings = Facts(self._module).get_facts(self.gather_subset, self.gather_network_resources)
        sflow_facts = facts['ansible_network_resources'].get('sflow')
        if not sflow_facts:
            return []
        return sflow_facts

    def execute_module(self):
        """ Execute the module

        :rtype: A dictionary
        :returns: The result from module execution
        """
        result = {'changed': False}
        warnings = list()

        existing_sflow_facts = self.get_sflow_facts()
        commands, requests = self.set_config(existing_sflow_facts)
        if commands and len(requests) > 0:
            if not self._module.check_mode:
                try:
                    edit_config(self._module, to_request(self._module, requests))
                except ConnectionError as exc:
                    self._module.fail_json(msg=str(exc), code=exc.errno)
            result['changed'] = True
        result['commands'] = commands
        changed_sflow_facts = self.get_sflow_facts()

        result['before'] = existing_sflow_facts
        if result['changed']:
            result['after'] = changed_sflow_facts

        result['warnings'] = warnings
        return result

    def set_config(self, existing_sflow_facts):
        """ Collect the configuration from the args passed to the module,
            collect the current configuration (as a dict from facts)

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        want = self._module.params['config']
        have = existing_sflow_facts

        resp = self.set_state(want, have)
        return to_list(resp)

    def set_state(self, want, have):
        """ Select the appropriate function based on the state provided

        :param want: the desired configuration as a dictionary
        :param have: the current configuration as a dictionary
        :rtype: A tuple
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration, and REST requests that do it
        """
        commands = []
        requests = []
        want = self.validate_normailze_config(want)
        state = self._module.params['state']
        if state == 'deleted':
            commands, requests = self._state_deleted(want, have)
        elif state == 'merged':
            commands, requests = self._state_merged(want, have)
        elif state == 'overridden':
            commands, requests = self._state_overridden(want, have)
        else:
            commands, requests = self._state_replaced(want, have)
        return commands, requests

    def _state_replaced(self, want, have):
        """ The command generator when state is replaced

        :rtype: A tuple of lists
        :returns: A list of what commands and state necessary to migrate the current configuration
                  to the desired configuration, and a list of requests needed to make changes
        """
        commands = []
        requests = []

        if len(want) == 0:
            # not wanting to replace anything we can just quit
            return commands, requests

        # very similar to override so using that code, one difference is don't want
        # replaced to delete sections that were not specified, so getting around that
        # by filling with existing have's values because override doesn't change matching settings
        if "agent" in have and "agent" not in want:
            want["agent"] = have["agent"]
        if "sampling_rate" in have and "sampling_rate" not in want:
            want["sampling_rate"] = have["sampling_rate"]
        if "polling_interval" in have and "polling_interval" not in want:
            want["polling_interval"] = have["polling_interval"]
        if "enabled" in have and "enabled" not in want:
            want["enabled"] = have["enabled"]
        if "interfaces" in have and "interfaces" not in want:
            want["interfaces"] = have["interfaces"]
        if "collectors" in have and "collectors" not in want:
            want["collectors"] = have["collectors"]

        commands, requests = self._state_overridden(want, have)

        if commands and len(requests) > 0:
            # since using a different state, if there are commands the method will record state
            # only one difference in resulting state
            for command_set in commands:
                if command_set["state"] == "overridden":
                    command_set["state"] = "repalced"
        else:
            commands = []
        return commands, requests

    def _state_overridden(self, want, have):
        """ The command generator when state is overridden

        :rtype: A tuple of lists
        :returns: A list of what commands and state necessary to migrate the current configuration
                  to the desired configuration, and a list of requests needed to make changes
        """
        commands = []
        requests = []

        self.fill_defaults(want)
        remove_diff = get_diff(have, want, test_keys=self.sflow_diff_test_keys)
        introduced_diff = get_diff(want, have, test_keys=self.sflow_diff_test_keys)

        remove_diff = self.find_substitution_deletes(remove_diff, introduced_diff)
        self.prep_merge_diff(introduced_diff, want)

        if remove_diff is not None and len(remove_diff) > 0:
            # deleted will take empty as clear all, override having empty remove differences is do nothing.
            # so need to check
            commands, requests = self._state_deleted(remove_diff, have)
        commandsTwo, requestsTwo = self._state_merged(introduced_diff, have)
        # combining two lists of changes
        if len(commands) == 0:
            # nothing was deleted, if changed or not just depends on merges
            commands = commandsTwo
        else:
            commandsTwo = update_states(commandsTwo, "overridden")
            commands.extend(commandsTwo)

        if len(requests) == 0:
            requests = requestsTwo
        else:
            requests.extend(requestsTwo)
        return commands, requests

    def _state_merged(self, want, have):
        """ The command generator when state is merged

        :rtype: A tuple of lists
        :returns: A list of what commands and state necessary to merge the provided into
                  the current configuration, and a list of requests needed to make changes
        """

        if not want:
            # nothing to do here
            return [], []

        commands = get_diff(want, have, test_keys=self.sflow_diff_test_keys)

        requests = self.create_patch_sflow_root_request(commands, [])

        if commands and len(requests) > 0:
            commands = update_states(commands, "merged")
        else:
            commands = []
        return commands, requests

    def _state_deleted(self, want, have):
        """ The command generator when state is deleted

        :rtype: A tuple of lists
        :returns: A list of what commands and state necessary to remove the current configuration
                  of the provided objects, and a list of requests needed to make changes
        """
        commands = {}
        requests = []

        # don't want to interpret none values. if want to delete all, empty lists or dicts must be passed

        if len(want) == 0:
            # for the "clear all config" instance. passing in empty dictionary to deleted means clear everything
            want = have

        if want.get("enabled") and have.get("enabled"):
            # default value is false so only need to do the "delete" (actually reset) if values are true and match
            commands.update({"enabled": have["enabled"]})
            requests.append({"path": "data/openconfig-sampling-sflow:sampling/sflow/config/enabled", "method": "PUT",
                             "data": {"openconfig-sampling-sflow:enabled": False}})

        if "polling_interval" in want and "polling_interval" in have and want["polling_interval"] == have["polling_interval"]:
            # want to make sure setting specified and match
            commands.update({"polling_interval": have["polling_interval"]})
            requests.append({"path": "data/openconfig-sampling-sflow:sampling/sflow/config/polling-interval", "method": "DELETE"})

        if "agent" in want and "agent" in have and want["agent"] == have["agent"]:
            commands.update({"agent": have["agent"]})
            requests.append({"path": "data/openconfig-sampling-sflow:sampling/sflow/config/agent", "method": "DELETE"})

        if "sampling_rate" in want and "sampling_rate" in have and want["sampling_rate"] == have["sampling_rate"]:
            commands.update({"sampling_rate": have["sampling_rate"]})
            requests.append({"path": "data/openconfig-sampling-sflow:sampling/sflow/config/sampling-rate", "method": "DELETE"})

        if ("collectors" in want or len(want) == 0) and "collectors" in have:
            # either clear all settings, all collectors or certain collectors here
            to_delete_list = have["collectors"]
            if len(want["collectors"]) > 0:
                # a specified non-empty list means no longer clear everything
                to_delete_list = want["collectors"]

            deleted_list = []

            have_collectors_dict = {(collector["address"], collector["network_instance"], collector["port"]): collector for collector in have["collectors"]}

            for collector in to_delete_list:
                found_match = (collector["address"], collector["network_instance"], collector["port"]) in have_collectors_dict
                if found_match:
                    deleted_list.append(have_collectors_dict[(collector["address"], collector["network_instance"], collector["port"])])
                    requests.append({"path": "data/openconfig-sampling-sflow:sampling/sflow/collectors/collector=" +
                                    collector["address"] + "," + str(collector["port"]) + "," +
                                    collector["network_instance"], "method": "DELETE"})
            if len(deleted_list) > 0:
                commands.update({"collectors": deleted_list})

        if ("interfaces" in want or len(want) == 0) and "interfaces" in have:
            # either clear all settings, all interfaces, or certain interfaces
            to_delete_list = have["interfaces"]
            if len(want["interfaces"]) > 0:
                # a specified non-empty list means no longer clear everything
                to_delete_list = want["interfaces"]

            deleted_list = []

            have_interfaces_dict = {interface["name"]: interface for interface in have["interfaces"]}

            for interface in to_delete_list:
                found_interface = interface["name"] in have_interfaces_dict

                if found_interface:
                    deleted_list.append(have_interfaces_dict[interface["name"]])
                    requests.append({"path": "data/openconfig-sampling-sflow:sampling/sflow/interfaces/interface=" + interface["name"], "method": "DELETE"})
            if len(deleted_list) > 0:
                commands.update({"interfaces": deleted_list})

        if commands and len(requests) > 0:
            commands = update_states(commands, "deleted")
        else:
            commands = []
        return commands, requests

    def validate_normailze_config(self, config):
        '''validates and normalizes interface names in passed in config
        :returns: config object that has been validated and normalized'''
        config = remove_none(config)
        validated_config = validate_config(self._module.argument_spec, {"config": config})
        # validation will add a bunch of Nones where values are missing in partially filled config dicts
        validated_config = remove_none(validated_config)
        if config is not None and config.get("polling_interval") is not None:
            if not (int(config["polling_interval"]) == 0 or int(config["polling_interval"]) in range(5, 301)):
                self._module.fail_json(msg="polling interval out of range. must be 0 or in the range 5-300 inclusive", code=1)
        if config is not None and config.get("agent") is not None:
            config["agent"] = get_normalize_interface_name(config.get("agent", ""), self._module)
        if config is not None and config.get("interfaces") is not None:
            for interface in config["interfaces"]:
                interface["name"] = get_normalize_interface_name(interface.get("name", ""), self._module)
        return validated_config["config"]

    def create_patch_sflow_root_request(self, to_update_config_dict, request_list):
        '''builds REST request for patching on sflow root endpoint, which can update all sflow information in one REST request.
        Uses given config as what needs to be updated without further checks. adds request to passed in request list and returns list'''

        method = "PATCH"
        root_data_key = "openconfig-sampling-sflow:sflow"

        if len(to_update_config_dict) == 0:
            return request_list

        request_body = {}
        has_data = False

        # config always requred in this endpoint
        request_body["config"] = self.create_config_request_body(to_update_config_dict)
        if len(request_body["config"]) > 0:
            has_data = True

        if "collectors" in to_update_config_dict:
            collector_body = self.create_collectors_list_request_body(to_update_config_dict)
            if len(collector_body) > 0:
                request_body.update({"collectors": {"collector": collector_body}})
                has_data = True

        if "interfaces" in to_update_config_dict:
            interface_body = self.create_interface_list_request_body(to_update_config_dict)
            if len(interface_body) > 0:
                request_body.update({"interfaces": {"interface": interface_body}})
                has_data = True

        if has_data:
            request_list.append({"path": self.sflow_uri, "method": method, "data": {root_data_key: request_body}})
        return request_list

    def create_config_request_body(self, config_dict):
        '''does format transformation and creates and returns dictionary that holds all sflow global settings that were passed in.
        Takes a dictionary in argspect format and returns the matching REST formatted fields for global config'''
        request_config = {}
        if "enabled" in config_dict:
            request_config["enabled"] = config_dict["enabled"]
        if "polling_interval" in config_dict:
            request_config["polling-interval"] = config_dict["polling_interval"]
        if "agent" in config_dict:
            request_config["agent"] = config_dict["agent"]
        if "sampling_rate" in config_dict:
            request_config["sampling-rate"] = config_dict["sampling_rate"]
        return request_config

    def create_collectors_list_request_body(self, config_dict):
        '''does format transformation and creates and returns a list of sflow collectors with the settings passed in.
        Takes a dictionary for all config in argspec format and returns the collectors listed in REST API format'''
        collector_list = []
        for collector in config_dict["collectors"]:
            collector_request = {"address": collector["address"],
                                 "network-instance": collector["network_instance"],
                                 "port": collector["port"]}
            # since REST needs the collector list item with its settings and a nested config with a copy of those same settings
            collector_request.update({"config": dict(collector_request)})
            collector_list.append(collector_request)
        return collector_list

    def create_interface_list_request_body(self, config_dict):
        '''does format transformation and creates and returns a list of sflow interfaces with the settings passed in.
        Takes a dictionary for all config in argspec format and returns all interfaces listed that have configuration. Returns list in REST API format'''
        interface_list = []
        for interface in config_dict["interfaces"]:
            interface_config_request = {}
            if "enabled" in interface:
                interface_config_request["enabled"] = interface["enabled"]
            if "sampling_rate" in interface:
                interface_config_request["sampling-rate"] = interface["sampling_rate"]
            if len(interface_config_request) == 0:
                # listed interface doesn't actually have any configured settings, but name is hanging around
                continue
            interface_config_request["name"] = interface["name"]
            interface_list.append({"name": interface["name"],
                                   "config": interface_config_request})
        return interface_list

    def fill_defaults(self, config):
        '''modifies the given original config object to add sflow default values that are missing. returns the config for chaining purposes'''
        if "enabled" not in config:
            config["enabled"] = False
        return config

    def find_substitution_deletes(self, remove_diff, introduced_diff):
        '''specifically for overridden and replaced states, finds and builds collection of which config settings need to be deleted and without anything that is
        getting replaced with new values. `get_diff` will return collection of both things that need to be deleted and things that will have new values.'''
        result = {}
        if "agent" in remove_diff and "agent" not in introduced_diff:
            result["agent"] = remove_diff["agent"]
        if "enabled" in remove_diff and "enabled" not in introduced_diff:
            result["enabled"] = remove_diff["enabled"]
        if "polling_interval" in remove_diff and "polling_interval" not in introduced_diff:
            result["polling_interval"] = remove_diff["polling_interval"]
        if "sampling_rate" in remove_diff and "sampling_rate" not in introduced_diff:
            result["sampling_rate"] = remove_diff["sampling_rate"]
        if "collectors" in remove_diff:
            result["collectors"] = remove_diff["collectors"]
        if "interfaces" in remove_diff:
            result["interfaces"] = remove_diff["interfaces"]
        return result

    def prep_merge_diff(self, diff, want):
        '''prep found collection of differences to add information that should be added that isn't in difference. This is caused by some settings
        being grouped and deleted at a parent level REST endpoint. some settings in group may match but were deleted together resulting in setting
        being missing from diff but needs to be added. Fills in any interfaces in diff with matching information in want'''
        if "interfaces" in diff:
            searched_test_keys = None
            for item in self.sflow_diff_test_keys:
                for k, v in item.items():
                    if k == "interfaces":
                        searched_test_keys = v
                        break
            want_index = build_ref_dict(want["interfaces"], searched_test_keys)
            for interface in diff["interfaces"]:
                item_key = find_item_key(interface, searched_test_keys)
                interface.update(want_index.get(item_key, {}))


def build_ref_dict(item_list, test_keys=None):
    '''helper for building a quick search dictionary for a list of dictionary or primitive config entries.
    uses list or the keys of a dictionary for finding the key for an item.
    If an item is found to appear more than once, merges dictionary config (doesn't merge any sub containers) and replaces existing values for other types
    helpful when config has a list of items with keys as fields in them and want to retrieve item with certain id without looping

    :param item_list: the list of config items to make a dictionary for, must have all fields used as part of the key present in item
    :param test_keys: list or dictionary of keys for what field's (or multiple fields') values identify an item.
        Or None if key is item itself (errors if item isn't hasable).
    :rtype: a dictionary
    :return: a dictionary where key is a tuple formed from the values of the key fields or the item itself
        and value is the item in the list with duplicate occurances merged.
        does not merge differences in nested dictionaries or lists'''
    # tested a bit with list of dictionaries of primitive values and list of strings
    search_dict = {}
    if item_list is None:
        return search_dict

    for item in item_list:
        item_key = find_item_key(item, test_keys)

        if item_key in search_dict:
            if isinstance(search_dict[item_key], dict):
                search_dict[item_key].update(item)
            else:
                search_dict[item_key] = item
        else:
            search_dict[item_key] = item
    return search_dict


def find_item_key(entry, test_keys=None):
    if test_keys is None:
        return deepcopy(entry)
    else:
        return tuple(entry[k] for k in test_keys)


def remove_none(config):
    '''goes through nested dictionary items and removes any keys that have None as value.
    enables using empty list/dict to specify clear everything for that section and differentiate this
    'clear everything' case from when no value was given
    remove_empties in ansible utils will remove empty lists and dicts as well as None'''
    if isinstance(config, dict):
        for k, v in list(config.items()):
            if v is not None:
                remove_none(v)
            if v is None:
                del config[k]
    elif isinstance(config, list):
        for item in list(config):
            if item is not None:
                remove_none(item)
            if item is None:
                config.remove(item)
    return config
