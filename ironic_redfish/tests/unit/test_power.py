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

import mock
import sushy

from ironic.common import states
from ironic.conductor import task_manager
from ironic.tests.unit.conductor import mgr_utils
from ironic.tests.unit.db import base as db_base
from ironic.tests.unit.objects import utils as obj_utils

import ironic_redfish
from ironic_redfish import power as redfish_power
from ironic_redfish import utils as redfish_utils


INFO_DICT = {
    "redfish_address": "https://example.com",
    "redfish_system_id": "/redfish/v1/Systems/FAKESYSTEM",
    "redfish_username": "username",
    "redfish_password": "password"
}


class MockedSushyError(Exception):
    pass


class RedfishPowerTestCase(db_base.DbTestCase):

    def setUp(self):
        super(RedfishPowerTestCase, self).setUp()
        self.config(enabled_drivers=['pxe_redfish'])
        mgr_utils.mock_the_extension_manager(
            driver='pxe_redfish', namespace='ironic.drivers')
        self.node = obj_utils.create_test_node(
            self.context, driver='pxe_redfish', driver_info=INFO_DICT)

    def test_get_properties(self):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            properties = task.driver.get_properties()
            for prop in redfish_utils.COMMON_PROPERTIES:
                self.assertIn(prop, properties)

    @mock.patch.object(redfish_utils, 'parse_driver_info', autospec=True)
    def test_validate(self, mock_parse_driver_info):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            task.driver.power.validate(task)
            mock_parse_driver_info.assert_called_once_with(task.node)

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_get_power_state(self, mock_get_system):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            expected_values = [
                (sushy.SYSTEM_POWER_STATE_ON, states.POWER_ON),
                (sushy.SYSTEM_POWER_STATE_POWERING_ON, states.POWER_ON),
                (sushy.SYSTEM_POWER_STATE_OFF, states.POWER_OFF),
                (sushy.SYSTEM_POWER_STATE_POWERING_OFF, states.POWER_OFF)
            ]
            for current, expected in expected_values:
                mock_get_system.return_value = mock.Mock(power_state=current)
                self.assertEqual(expected,
                                 task.driver.power.get_power_state(task))
                mock_get_system.assert_called_once_with(task.node)
                mock_get_system.reset_mock()

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_set_power_state(self, mock_get_system):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            expected_values = [
                (states.POWER_ON, sushy.RESET_ON),
                (states.POWER_OFF, sushy.RESET_FORCE_OFF),
                (states.REBOOT, sushy.RESET_FORCE_RESTART),
            ]

            fake_system = mock_get_system.return_value
            for target, expected in expected_values:
                task.driver.power.set_power_state(task, target)

                # Asserts
                fake_system.reset_system.assert_called_once_with(expected)
                mock_get_system.assert_called_once_with(task.node)

                # Reset mocks
                fake_system.reset_system.reset_mock()
                mock_get_system.reset_mock()

    @mock.patch.object(redfish_power, 'sushy')
    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_set_power_state_fail(self, mock_get_system, mock_sushy):
        fake_system = mock_get_system.return_value
        mock_sushy.exceptions.SushyError = MockedSushyError
        fake_system.reset_system.side_effect = MockedSushyError()

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaisesRegex(
                ironic_redfish.RedfishError, 'Redfish set power state',
                task.driver.power.set_power_state, task, states.POWER_ON)
            fake_system.reset_system.assert_called_once_with(
                sushy.RESET_ON)
            mock_get_system.assert_called_once_with(task.node)

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_reboot(self, mock_get_system):
        fake_system = mock_get_system.return_value
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            expected_values = [
                (sushy.SYSTEM_POWER_STATE_ON, sushy.RESET_FORCE_RESTART),
                (sushy.SYSTEM_POWER_STATE_OFF, sushy.RESET_ON)
            ]

            for current, expected in expected_values:
                fake_system.power_state = current
                task.driver.power.reboot(task)

                # Asserts
                fake_system.reset_system.assert_called_once_with(expected)
                mock_get_system.assert_called_once_with(task.node)

                # Reset mocks
                fake_system.reset_system.reset_mock()
                mock_get_system.reset_mock()

    @mock.patch.object(redfish_power, 'sushy')
    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_reboot_fail(self, mock_get_system, mock_sushy):
        fake_system = mock_get_system.return_value
        mock_sushy.exceptions.SushyError = MockedSushyError
        fake_system.reset_system.side_effect = MockedSushyError()

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            fake_system.power_state = sushy.SYSTEM_POWER_STATE_ON
            self.assertRaisesRegex(
                ironic_redfish.RedfishError, 'Redfish reboot failed',
                task.driver.power.reboot, task)
            fake_system.reset_system.assert_called_once_with(
                sushy.RESET_FORCE_RESTART)
            mock_get_system.assert_called_once_with(task.node)

    def test_get_supported_power_states(self):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            supported_power_states = (
                task.driver.power.get_supported_power_states(task))
            self.assertEqual(list(redfish_power.SET_POWER_STATE_MAP),
                             supported_power_states)
