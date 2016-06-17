########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#


from os import path
import unittest

from cloudify.test_utils import workflow_test


class TestPlugin(unittest.TestCase):

    @workflow_test(
        path.join('blueprint',
                  # 'blueprint.yaml'
                  # 'blueprint-ecs.yaml'
                  # 'blueprint-ecs-has-exist.yaml'
                  # 'blueprint-ecs-eip.yaml'
                  # 'blueprint-ecs-eip-no-subnet.yaml'
                  # 'blueprint-slb.yaml'
                  'blueprint-sg.yaml'
                  ),
        resources_to_copy=[path.join('blueprint', 'plugin.yaml'),
                           path.join('blueprint', 'types.yaml')]
                   )
    def test_my_task(self, cfy_local):
        # execute install workflow
        """

        :param cfy_local:
        """
        cfy_local.execute('install', task_retries=2)

        # extract node instances
        instances = cfy_local.storage.get_node_instances()
        for instance in instances:
            print instance.id
            print instance.runtime_properties
        print cfy_local.outputs()

        """
        cfy_local.execute('uninstall', task_retries=2)
        instances = cfy_local.storage.get_node_instances()
        for instance in instances:
            self.assertNotIn('aliyun_resource_id',
                             instance.runtime_properties
                             )
        print cfy_local.outputs()
        """
