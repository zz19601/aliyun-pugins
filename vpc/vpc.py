########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports

from . import constants
from core.base import AliyunBaseNode
from aliyunsdkecs.request.v20140526 import \
    DescribeVpcsRequest, CreateVpcRequest, DeleteVpcRequest

# Cloudify imports
from cloudify import ctx
# from cloudify import compute
# from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    return Vpc().creation_validation()


@operation
def create(**_):
    return Vpc().created_async()


@operation
def delete(**_):
    return Vpc().deleted()


class Vpc(AliyunBaseNode):

    def __init__(self):
        super(Vpc, self).__init__(
            constants.VPC['ALIYUN_RESOURCE_TYPE'],
            constants.VPC['REQUIRED_PROPERTIES']
        )
        self.list_response_keys = \
            {'Items': 'Vpcs',
                'Item': 'Vpc',
                'ItemId': 'VpcId',
                'TotalCount': 'TotalCount'}

    def get_query_resource_request(self, list_of_ids=None):
        queryVPC = DescribeVpcsRequest.DescribeVpcsRequest()
        if list_of_ids and len(list_of_ids) > 0:
            queryVPC.set_VpcId(list_of_ids[0])
        return queryVPC

    def create(self):
        request = CreateVpcRequest.CreateVpcRequest()
        if ctx.node.properties['cidr_block']:
            request.set_CidrBlock(ctx.node.properties['cidr_block'])
        if 'vpc_name' in ctx.node.properties:
            request.set_VpcName(ctx.node.properties['vpc_name'])
        if 'description' in ctx.node.properties:
            request.set_Description()
        if 'user_cidr' in ctx.node.properties:
            request.set_UserCidr(ctx.node.properties['user_cidr'])
        vpc = self.execute(request, raise_on_falsy=True)
        self.resource_id = vpc['VpcId']

        return True

    def set_runtime_properties(self, vpc):
        ctx.instance.runtime_properties['VRouterId'] = vpc['VRouterId']
        ctx.instance.runtime_properties['RegionId'] = vpc['RegionId']
        if 'RouteTableId' in vpc:
            ctx.instance.runtime_properties['RouteTableId'] = \
                vpc['RouteTableId']

    def delete(self):
        request = DeleteVpcRequest.DeleteVpcRequest()
        request.set_VpcId(self.resource_id)
        self.execute(request, raise_on_falsy=True)
        return True
