########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#


# instance module constants
INSTANCE_STATE_STARTED = 'Running'
# INSTANCE_STATE_TERMINATED = 'Terminated'  # ?
INSTANCE_STATE_STOPPED = 'Stopped'

INSTANCE = dict(
    ALIYUN_RESOURCE_TYPE='ecs',
    CLOUDIFY_NODE_TYPE='cloudify.aliyun.nodes.Instance',
    ID_FORMAT='^i\-[0-9a-z]{9}$',
    REQUIRED_PROPERTIES=['image_id', 'instance_type']
)

ELASTICIP = dict(
    ALIYUN_RESOURCE_TYPE='eip',
    CLOUDIFY_NODE_TYPE='cloudify.aliyun.nodes.ElasticIP',
    ID_FORMAT='^eip\-[0-9a-z]{9}$',
    REQUIRED_PROPERTIES=[]
)

SLB = dict(
    ALIYUN_RESOURCE_TYPE='slb',
    CLOUDIFY_NODE_TYPE='cloudify.aliyun.nodes.ServerLoadBalancer',
    # 15542b8c7fb-cn-beijing-btc-a01 lb2ze8e8b542ta01pfk4
    ID_FORMAT='^[-0-9a-z]{10,50}$',
    REQUIRED_PROPERTIES=['listeners']
)

SECURITY_GROUP = dict(
    ALIYUN_RESOURCE_TYPE='sg',
    CLOUDIFY_NODE_TYPE='cloudify.aliyun.nodes.SecurityGroup',
    ID_FORMAT='^eip\-[0-9a-z]{9}$',
    REQUIRED_PROPERTIES=['rules']
)


# relationships
INSTANCE_SECURITY_GROUP_RELATIONSHIP = 'instance_connected_to_security_group'
INSTANCE_KEYPAIR_RELATIONSHIP = 'instance_connected_to_keypair'
INSTANCE_SUBNET_RELATIONSHIP = 'instance_contained_in_subnet'
SECURITY_GROUP_VPC_RELATIONSHIP = 'security_group_contained_in_vpc'
SLB_SUBNET_RELATIONSHIP = 'slb_contained_in_subnet'

# securitygroup module constants
SECURITY_GROUP_REQUIRED_PROPERTIES = ['rules']

# ELB Default Values: todo
HEALTH_CHECK_INTERVAL = 30
HEALTH_CHECK_HEALTHY_THRESHOLD = 3
HEALTH_CHECK_TIMEOUT = 5
HEALTH_CHECK_UNHEALTHY_THRESHOLD = 5

SLB_REQUIRED_PROPERTIES = ['slb_name',  'listeners']

# disk module constants
VOLUME_REQUIRED_PROPERTIES = ['size', 'zone']
VOLUME_SNAPSHOT_ATTRIBUTE = 'snapshots_ids'
VOLUME_AVAILABLE = 'available'
VOLUME_CREATING = 'creating'
VOLUME_IN_USE = 'in-use'

# keypair module constants
KEYPAIR_REQUIRED_PROPERTIES = ['private_key_path']

# elastic ip module contants
ALLOCATION_ID = 'allocation_id'

# config
ALIYUN_CONFIG_PROPERTY = 'aliyun_config'
ALIYUN_DEFAULT_CONFIG_PATH = '~/.aliyuncli'
EXTERNAL_RESOURCE_ID = 'aliyun_resource_id'
NODE_INSTANCE = 'node-instance'
RELATIONSHIP_INSTANCE = 'relationship-instance'
ALIYUN_CONFIG_PATH_ENV_VAR_NAME = "ALIYUN_CONFIG_PATH"

# aliyuncli config schema (section > options)
ALIYUNCLI_CONFIG_SCHEMA = {
    'default': ['region', 'aliyun_access_key_id', 'aliyun_access_key_secret'],
}
