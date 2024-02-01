#
# -*- coding: utf-8 -*-
# Copyright 2023 Dell Inc. or its subsidiaries. All Rights Reserved
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

#############################################
#                WARNING                    #
#############################################
#
# This file is auto generated by the resource
#   module builder playbook.
#
# Do not edit this file manually.
#
# Changes to this file will be over written
#   by the resource module builder.
#
# Changes should be made in the model used to
#   generate this file or in the resource module
#   builder template.
#
#############################################

"""
The arg spec for the sonic_dhcp_snooping module
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


class Dhcp_snoopingArgs(object):  # pylint: disable=R0903
    """The arg spec for the sonic_dhcp_snooping module"""

    def __init__(self, **kwargs):
        pass

    argument_spec = {
        'config': {
            'options': {
                'afis': {
                    'elements': 'dict',
                    'options': {
                        'afi': {
                            'choices': ['ipv4', 'ipv6'],
                            'required': True,
                            'type': 'str',
                        },
                        'enabled': {'type': 'bool'},
                        'source_bindings': {
                            'elements': 'dict',
                            'options': {
                                'mac_addr': {'required': True, 'type': 'str'},
                                'ip_addr': {'type': 'str'},
                                'intf_name': {'type': 'str'},
                                'vlan_id': {'type': 'int'},
                            },
                            'type': 'list',
                        },
                        'trusted': {
                            'elements': 'dict',
                            'options': {
                                'intf_name': {'required': True, 'type': 'str'},
                            },
                            'type': 'list',
                        },
                        'verify_mac': {'type': 'bool'},
                        'vlans': {'elements': 'str', 'type': 'list'},
                    },
                    'type': 'list',
                }
            },
            'type': 'dict',
        },
        'state': {
            'choices': ['merged', 'deleted', 'overridden', 'replaced'],
            'default': 'merged',
            'type': 'str',
        },
    }  # pylint: disable=C0301