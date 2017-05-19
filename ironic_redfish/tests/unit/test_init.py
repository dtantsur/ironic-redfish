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

from ironic.conductor import task_manager
from ironic.drivers.modules import iscsi_deploy
from ironic.drivers.modules import pxe
from ironic.tests.unit.db import base as db_base
from ironic.tests.unit.objects import utils as obj_utils

from ironic_redfish import management as redfish_mgmt
from ironic_redfish import power as redfish_power


class RedfishDriverTestCase(db_base.DbTestCase):

    def setUp(self):
        super(RedfishDriverTestCase, self).setUp()
        self.config(enabled_drivers=['pxe_redfish'])

    def test_driver(self):
        node = obj_utils.create_test_node(self.context, driver='pxe_redfish')
        with task_manager.acquire(self.context, node.id) as task:
            self.assertIsInstance(task.driver.management,
                                  redfish_mgmt.RedfishManagement)
            self.assertIsInstance(task.driver.power,
                                  redfish_power.RedfishPower)
            self.assertIsInstance(task.driver.boot, pxe.PXEBoot)
            self.assertIsInstance(task.driver.deploy, iscsi_deploy.ISCSIDeploy)
