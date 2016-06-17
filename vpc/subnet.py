########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports

from . import constants
from ecs import constants as ecs_constants
from core.base import AliyunBaseNode
from aliyunsdkecs.request.v20140526 import DescribeVSwitchesRequest, \
    CreateVSwitchRequest, DeleteVSwitchRequest, DescribeZonesRequest

# Cloudify imports
from cloudify import ctx
# from cloudify import compute
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    return Subnet().creation_validation()


@operation
def create(**_):
    return Subnet().created_async()


@operation
def delete(**_):
    return Subnet().deleted()


# for get AvaliabilityZones of some region
class AvaliabilityZone(AliyunBaseNode):

    def __init__(self, region_id):
        super(AvaliabilityZone, self).__init__(
            'AvaliabilityZone', [])
        self._region_id = region_id
        self.list_response_keys = \
            {'Items': 'Zones',
                'Item': 'Zone',
                'ItemId': 'ZoneId',
                'TotalCount': ''}  # not return TotalCount

    def get_query_resource_request(self, list_of_ids=None):
        self.client.set_region_id(self._region_id)
        zoneRequest = DescribeZonesRequest.DescribeZonesRequest()
        return zoneRequest


class Subnet(AliyunBaseNode):

    def __init__(self):
        super(Subnet, self).__init__(
            constants.SUBNET['ALIYUN_RESOURCE_TYPE'],
            constants.SUBNET['REQUIRED_PROPERTIES']
        )
        self.list_response_keys = \
            {'Items': 'VSwitches',
                'Item': 'VSwitch',
                'ItemId': 'VSwitchId',
                'TotalCount': 'TotalCount'}
        is_instance = ctx.type == ecs_constants.NODE_INSTANCE
        instance = ctx.instance if is_instance else ctx.source.instance
        # get vpc instance
        vpc_instances = self.get_target_instances_of_relationship_type(
            constants.SUBNET_IN_VPC, instance.relationships)
        if len(vpc_instances) == 0:
            raise NonRecoverableError(
                'subnet must be connected to one vpc')
        if len(vpc_instances) > 1:
            raise NonRecoverableError(
                'subnet can only be connected to one vpc')
        self._vpcid = self.get_external_resource_id(vpc_instances[0])
        self._vpc_region_id = vpc_instances[0].runtime_properties.get(
            'RegionId')

    def get_query_resource_request(self, list_of_ids=None):
        queryVSwitch = DescribeVSwitchesRequest.DescribeVSwitchesRequest()
        # need VpcId param
        queryVSwitch.set_VpcId(self._vpcid)
        if list_of_ids and len(list_of_ids) > 0:
            queryVSwitch.set_VSwitchId(list_of_ids[0])
        return queryVSwitch

    def create(self):
        createRequest = CreateVSwitchRequest.CreateVSwitchRequest()
        self._set_creation_args(createRequest)
        vSwitch = self.execute(createRequest, raise_on_falsy=True)
        self.resource_id = vSwitch[self.list_response_keys['ItemId']]
        # set zoneid runtime property
        zone_id = createRequest.get_ZoneId()
        ctx.instance.runtime_properties['availability_zone'] = zone_id
        return True

    def _set_creation_args(self, createRequest):
        createRequest.set_VpcId(self._vpcid)
        createRequest.set_CidrBlock(ctx.node.properties['cidr_block'])
        zone_id = None
        if 'availability_zone' in ctx.node.properties:
            zone_id = ctx.node.properties['availability_zone']
        if not zone_id:
            # get first zone of VPC region
            zones = AvaliabilityZone(self._vpc_region_id).get_all_matching()
            if len(zones) == 0:
                raise NonRecoverableError('cannot get zone')
            zone_id = zones[0]['ZoneId']
        createRequest.set_ZoneId(zone_id)
        if 'name' in ctx.node.properties:
            createRequest.set_VSwitchName(ctx.node.properties['name'])
        if 'description' in ctx.node.properties:
            createRequest.set_Description(ctx.node.properties['description'])

    def delete(self):
        delereRequest = DeleteVSwitchRequest.DeleteVSwitchRequest()
        delereRequest.set_VSwitchId(self.resource_id)
        self.execute(delereRequest, raise_on_falsy=True)
        return True
