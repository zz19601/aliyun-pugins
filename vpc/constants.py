########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

EXTERNAL_RESOURCE_ID = 'aliyun_resource_id'
AVAILABILITY_ZONE = 'availability_zone'
ALIYUN_CONFIG_PROPERTY = 'aliyun_config'


VPC = dict(
    ALIYUN_RESOURCE_TYPE='vpc',
    CLOUDIFY_NODE_TYPE='cloudify.aliyun.nodes.VPC',
    ID_FORMAT='^vpc\-[0-9a-z]{9}$',
    REQUIRED_PROPERTIES=[]
)

SUBNET = dict(
    ALIYUN_RESOURCE_TYPE='vSwitch',
    CLOUDIFY_NODE_TYPE='cloudify.aliyun.nodes.Subnet',
    ID_FORMAT='^vsw\-[0-9a-z]{9}$',
    REQUIRED_PROPERTIES=['cidr_block']
)


SUBNET_IN_VPC = \
    'subnet_contained_in_vpc'
