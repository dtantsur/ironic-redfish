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

from ironic.common import boot_devices
from ironic.conductor import task_manager
from ironic.tests.unit.conductor import mgr_utils
from ironic.tests.unit.db import base as db_base
from ironic.tests.unit.objects import utils as obj_utils

import ironic_redfish
from ironic_redfish import management as redfish_mgmt
from ironic_redfish import utils as redfish_utils


INFO_DICT = {
    "redfish_address": "https://example.com",
    "redfish_system_id": "/redfish/v1/Systems/FAKESYSTEM",
    "redfish_username": "username",
    "redfish_password": "password"
}


class MockedSushyError(Exception):
    pass


class RedfishManagementTestCase(db_base.DbTestCase):

    def setUp(self):
        super(RedfishManagementTestCase, self).setUp()
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
            task.driver.management.validate(task)
            mock_parse_driver_info.assert_called_once_with(task.node)

    def test_get_supported_boot_devices(self):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            supported_boot_devices = (
                task.driver.management.get_supported_boot_devices(task))
            self.assertEqual(list(redfish_mgmt.BOOT_DEVICE_MAP_REV),
                             supported_boot_devices)

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_set_boot_device(self, mock_get_system):
        fake_system = mock.Mock()
        mock_get_system.return_value = fake_system
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            expected_values = [
                (boot_devices.PXE, sushy.BOOT_SOURCE_TARGET_PXE),
                (boot_devices.DISK, sushy.BOOT_SOURCE_TARGET_HDD),
                (boot_devices.CDROM, sushy.BOOT_SOURCE_TARGET_CD),
                (boot_devices.BIOS, sushy.BOOT_SOURCE_TARGET_BIOS_SETUP)
            ]

            for target, expected in expected_values:
                task.driver.management.set_boot_device(task, target)

                # Asserts
                fake_system.set_system_boot_source.assert_called_once_with(
                    expected, enabled=sushy.BOOT_SOURCE_ENABLED_ONCE)
                mock_get_system.assert_called_once_with(task.node)

                # Reset mocks
                fake_system.set_system_boot_source.reset_mock()
                mock_get_system.reset_mock()

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_set_boot_device_persistency(self, mock_get_system):
        fake_system = mock.Mock()
        mock_get_system.return_value = fake_system
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            expected_values = [
                (True, sushy.BOOT_SOURCE_ENABLED_CONTINUOUS),
                (False, sushy.BOOT_SOURCE_ENABLED_ONCE)
            ]

            for target, expected in expected_values:
                task.driver.management.set_boot_device(
                    task, boot_devices.PXE, persistent=target)

                fake_system.set_system_boot_source.assert_called_once_with(
                    sushy.BOOT_SOURCE_TARGET_PXE, enabled=expected)
                mock_get_system.assert_called_once_with(task.node)

                # Reset mocks
                fake_system.set_system_boot_source.reset_mock()
                mock_get_system.reset_mock()

    @mock.patch.object(redfish_mgmt, 'sushy')
    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_set_boot_device_fail(self, mock_get_system, mock_sushy):
        fake_system = mock.Mock()
        mock_sushy.exceptions.SushyError = MockedSushyError
        fake_system.set_system_boot_source.side_effect = MockedSushyError
        mock_get_system.return_value = fake_system
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaisesRegex(
                ironic_redfish.RedfishError, 'Redfish set boot device',
                task.driver.management.set_boot_device, task, boot_devices.PXE)
            fake_system.set_system_boot_source.assert_called_once_with(
                sushy.BOOT_SOURCE_TARGET_PXE,
                enabled=sushy.BOOT_SOURCE_ENABLED_ONCE)
            mock_get_system.assert_called_once_with(task.node)

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_get_boot_device(self, mock_get_system):
        boot_attribute = {
            'target': sushy.BOOT_SOURCE_TARGET_PXE,
            'enabled': sushy.BOOT_SOURCE_ENABLED_CONTINUOUS
        }
        fake_system = mock.Mock(boot=boot_attribute)
        mock_get_system.return_value = fake_system
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            response = task.driver.management.get_boot_device(task)
            expected = {'boot_device': boot_devices.PXE,
                        'persistent': True}
            self.assertEqual(expected, response)

    def test_get_sensors_data(self):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            self.assertRaises(NotImplementedError,
                              task.driver.management.get_sensors_data, task)

    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_inject_nmi(self, mock_get_system):
        fake_system = mock.Mock()
        mock_get_system.return_value = fake_system
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.management.inject_nmi(task)
            fake_system.reset_system.assert_called_once_with(sushy.RESET_NMI)
            mock_get_system.assert_called_once_with(task.node)

    @mock.patch.object(redfish_mgmt, 'sushy')
    @mock.patch.object(redfish_utils, 'get_system', autospec=True)
    def test_inject_nmi_fail(self, mock_get_system, mock_sushy):
        fake_system = mock.Mock()
        mock_sushy.exceptions.SushyError = MockedSushyError
        fake_system.reset_system.side_effect = MockedSushyError
        mock_get_system.return_value = fake_system
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaisesRegex(
                ironic_redfish.RedfishError, 'Redfish inject NMI',
                task.driver.management.inject_nmi, task)
            fake_system.reset_system.assert_called_once_with(
                mock_sushy.RESET_NMI)
            mock_get_system.assert_called_once_with(task.node)
