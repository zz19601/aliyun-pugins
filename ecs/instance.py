########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports
from aliyunsdkecs.request.v20140526 import \
    DescribeInstancesRequest, CreateInstanceRequest, DeleteInstanceRequest, \
    StartInstanceRequest, StopInstanceRequest

from core.base import AliyunBaseNode
from . import constants, utils

# Cloudify imports
from cloudify import ctx
# from cloudify import compute
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    return Instance().creation_validation()


@operation
def create(**_):
    return Instance().created_async()


@operation
def start(**_):
    return Instance().start_async()


@operation
def stop(**_):
    return Instance().stop_async()


@operation
def delete(**_):
    return Instance().delete_async()


class Instance(AliyunBaseNode):

    def __init__(self):
        super(Instance, self).__init__(
            constants.INSTANCE['ALIYUN_RESOURCE_TYPE'],
            constants.INSTANCE['REQUIRED_PROPERTIES']
        )
        self.list_response_keys = \
            {'Items': 'Instances',
                'Item': 'Instance',
                'ItemId': 'InstanceId',
                'TotalCount': 'TotalCount'}

        self.create_ready_status = ['Stopped', 'Running']
        is_instance = ctx.type == constants.NODE_INSTANCE
        if not self.is_external_resource and is_instance:
            # get vSwitchID if contained in subnet
            subnet_instances = self.get_target_instances_of_relationship_type(
                constants.INSTANCE_SUBNET_RELATIONSHIP,
                ctx.instance.relationships)
            if len(subnet_instances) > 1:
                raise NonRecoverableError(
                    'instance may only be attached to one subnet')
            self._VSwitchid = None
            if len(subnet_instances) == 1:
                self._VSwitchid = self.get_external_resource_id(
                    subnet_instances[0])

        if not self.is_external_resource and is_instance:
            # get security_group ids from relation
            security_groups = self.get_target_instances_of_relationship_type(
                constants.INSTANCE_SECURITY_GROUP_RELATIONSHIP,
                ctx.instance.relationships)
            # must have security group ?
            self._security_group_ids = []
            for group in security_groups:
                self._security_group_ids.append(
                    self.get_external_resource_id(group))
            # append agents_security_group ids
            asg = 'agents_security_group'
            if 'parameters' in ctx.node.properties:
                if asg in ctx.node.properties['parameters']:
                    self._security_group_ids.append(
                        ctx.node.properties['parameters'][asg])

    def get_query_resource_request(self, list_of_ids=None):
        queryInstances = DescribeInstancesRequest.DescribeInstancesRequest()
        if list_of_ids and len(list_of_ids) > 0:
            queryInstances.set_InstanceIds(str(list_of_ids))
        return queryInstances

    def create(self):
        request = CreateInstanceRequest.CreateInstanceRequest()
        request.set_ImageId(ctx.node.properties['image_id'])
        request.set_InstanceType(ctx.node.properties['instance_type'])
        if self._VSwitchid:
            request.set_VSwitchId(self._VSwitchid)
        # todo: SecurityGroupId, not support multi when create
        # process in relation?
        if len(self._security_group_ids) > 0:
            request.set_SecurityGroupId(self._security_group_ids[0])
        if 'name' in ctx.node.properties:
            request.set_InstanceName(ctx.node.properties['name'])

        # other properties in parameters
        if 'parameters' in ctx.node.properties:
            for key, value in ctx.node.properties['parameters'].items():
                set_function = getattr(
                    request, 'set_' + key.replace('.', ''), None)
                if set_function:
                    set_function(value)

        instance = self.execute(request, raise_on_falsy=True)
        # Note: it is unicode string, such as u'i-25b2erpyd'
        # it will has error in ecs sdk list params: [u'i-25b2erpyd']
        # so encode as non-unicode, utf-8 or ansi is ok:
        self.resource_id = instance['InstanceId'].encode('utf-8')
        return True

    def set_runtime_properties(self, instance):
        ctx.instance.runtime_properties['RegionId'] = instance['RegionId']
        ctx.instance.runtime_properties['ZoneId'] = instance['ZoneId']
        ctx.instance.runtime_properties['VpcId'] = \
            instance['VpcAttributes']['VpcId']
        ctx.instance.runtime_properties['VSwitchId'] = \
            instance['VpcAttributes']['VSwitchId']

        # todo: if classic network and has public ip,
        # AllocatePublicIpAddress here
        # so that it will take effect when running
        # if AllocatePublicIpAddress when running, it will need restart

    def set_runtime_properties_when_running(self, instance):
        if len(instance['VpcAttributes']['VpcId']) > 0:
            # ip, private
            ips = instance['VpcAttributes']['PrivateIpAddress']['IpAddress']
            if len(ips) > 0:
                ctx.instance.runtime_properties['ip'] = \
                    ips[0]
            # public_ip_address
            if len(instance['EipAddress']['IpAddress']) > 0:
                ctx.instance.runtime_properties['public_ip_address'] = \
                    instance['EipAddress']['IpAddress'][0]
        else:  # classic network
            # ip, private
            if len(instance['InnerIpAddress']['IpAddress']) > 0:
                ctx.instance.runtime_properties['ip'] = \
                    instance['InnerIpAddress']['IpAddress'][0]
            # public_ip_address
            if len(instance['PublicIpAddress']['IpAddress']) > 0:
                ctx.instance.runtime_properties['public_ip_address'] = \
                    instance['PublicIpAddress']['IpAddress'][0]

    def unset_runtime_properties_when_running(self):
        for prop in ['ip', 'public_ip_address']:
            utils.unassign_runtime_property_from_resource(prop, ctx.instance)

    def start_async(self):
        resource = self.get_resource()
        # ctx.logger.info('resource:{0}'.format(resource))

        # note: resource['Status'] is 'Running' will not work!
        # resource['Status'] = u'Running', u'Running' is 'Running' is False
        # but u'Running' == 'Running' is True
        if resource['Status'] == 'Running':
            self.set_runtime_properties_when_running(resource)
            return True

        if resource['Status'] == 'Stopped':
            self.start_instance()

        return ctx.operation.retry(
            message='Waiting server to be running. Retrying...')

    def stop_async(self):
        if self.is_external_resource:
            # do not stop extern resource
            self.unset_runtime_properties_when_running()
            return True

        resource = self.get_resource()
        if resource['Status'] == 'Stopped':
            self.unset_runtime_properties_when_running()
            return True

        ctx.logger.info('status:{0}'.format(resource['Status']))
        if resource['Status'] == 'Running':
            self.stop_instance()

        return ctx.operation.retry(
            message='Waiting server to stop. Retrying...')

    def delete_async(self):
        if self.is_external_resource:
            # do not delete extern resource
            return self.post_delete()

        resource = self.get_resource()
        if not resource:  # deleted
            return self.post_delete()

        if resource['Status'] == 'Running':
            raise NonRecoverableError(
                'Instance is running, cannot delete it!')

        if resource['Status'] == 'Stopped':
            self.delete()

        return ctx.operation.retry(
            message='Waiting server to delete. Retrying...')

    def stop_instance(self):
        request = StopInstanceRequest.StopInstanceRequest()
        request.set_InstanceId(self.resource_id)
        self.execute(request, raise_on_falsy=True)
        return True

    def delete(self):
        request = DeleteInstanceRequest.DeleteInstanceRequest()
        request.set_InstanceId(self.resource_id)
        self.execute(request, raise_on_falsy=True)
        return True

    def start_instance(self):
        request = StartInstanceRequest.StartInstanceRequest()
        request.set_InstanceId(self.resource_id)
        self.execute(request, raise_on_falsy=True)
        return True
