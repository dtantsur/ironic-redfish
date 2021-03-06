# Copyright 2017 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log
import sushy

from ironic.common.i18n import _
from ironic.common import states
from ironic.conductor import task_manager
from ironic.drivers import base

import ironic_redfish
from ironic_redfish import utils as redfish_utils

LOG = log.getLogger(__name__)

GET_POWER_STATE_MAP = {
    sushy.SYSTEM_POWER_STATE_ON: states.POWER_ON,
    sushy.SYSTEM_POWER_STATE_POWERING_ON: states.POWER_ON,
    sushy.SYSTEM_POWER_STATE_OFF: states.POWER_OFF,
    sushy.SYSTEM_POWER_STATE_POWERING_OFF: states.POWER_OFF
}

SET_POWER_STATE_MAP = {
    states.POWER_ON: sushy.RESET_ON,
    states.POWER_OFF: sushy.RESET_FORCE_OFF,
    states.REBOOT: sushy.RESET_FORCE_RESTART,
}


class RedfishPower(base.PowerInterface):

    def get_properties(self):
        """Return the properties of the interface.

        :returns: dictionary of <property name>:<property description> entries.
        """
        return redfish_utils.COMMON_PROPERTIES.copy()

    def validate(self, task):
        """Validates the driver information needed by the redfish driver.

        :param task: a TaskManager instance containing the node to act on.
        :raises: InvalidParameterValue on malformed parameter(s)
        :raises: MissingParameterValue on missing parameter(s)
        """
        redfish_utils.parse_driver_info(task.node)

    def get_power_state(self, task):
        """Get the current power state of the task's node.

        :param task: a TaskManager instance containing the node to act on.
        :returns: a power state. One of :mod:`ironic.common.states`.
        :raises: InvalidParameterValue on malformed parameter(s)
        :raises: MissingParameterValue on missing parameter(s)
        :raises: RedfishConnectionError when it fails to connect to Redfish
        :raises: RedfishError on an error from the Sushy library
        """
        system = redfish_utils.get_system(task.node)
        return GET_POWER_STATE_MAP.get(system.power_state)

    @task_manager.require_exclusive_lock
    def set_power_state(self, task, power_state, timeout=None):
        """Set the power state of the task's node.

        :param task: a TaskManager instance containing the node to act on.
        :param power_state: Any power state from :mod:`ironic.common.states`.
        :param timeout: Not used by this driver.
        :raises: MissingParameterValue if a required parameter is missing.
        :raises: RedfishConnectionError when it fails to connect to Redfish
        :raises: RedfishError on an error from the Sushy library
        """
        system = redfish_utils.get_system(task.node)
        try:
            system.reset_system(SET_POWER_STATE_MAP.get(power_state))
        except sushy.exceptions.SushyError as e:
            error_msg = (_('Redfish set power state failed for node '
                           '%(node)s. Error: %(error)s') %
                         {'node': task.node.uuid, 'error': e})
            LOG.error(error_msg)
            raise ironic_redfish.RedfishError(error=error_msg)

    @task_manager.require_exclusive_lock
    def reboot(self, task, timeout=None):
        """Perform a hard reboot of the task's node.

        :param task: a TaskManager instance containing the node to act on.
        :param timeout: Not used by this driver.
        :raises: MissingParameterValue if a required parameter is missing.
        :raises: RedfishConnectionError when it fails to connect to Redfish
        :raises: RedfishError on an error from the Sushy library
        """
        system = redfish_utils.get_system(task.node)
        current_power_state = GET_POWER_STATE_MAP.get(system.power_state)

        try:
            if current_power_state == states.POWER_ON:
                system.reset_system(SET_POWER_STATE_MAP.get(states.REBOOT))
            else:
                system.reset_system(SET_POWER_STATE_MAP.get(states.POWER_ON))
        except sushy.exceptions.SushyError as e:
            error_msg = (_('Redfish reboot failed for node %(node)s. '
                           'Error: %(error)s') % {'node': task.node.uuid,
                                                  'error': e})
            LOG.error(error_msg)
            raise ironic_redfish.RedfishError(error=error_msg)

    def get_supported_power_states(self, task):
        """Get a list of the supported power states.

        :param task: A TaskManager instance containing the node to act on.
            Not used by this driver at the moment.
        :returns: A list with the supported power states defined
                  in :mod:`ironic.common.states`.
        """
        return list(SET_POWER_STATE_MAP)
