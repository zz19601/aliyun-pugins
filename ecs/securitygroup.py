########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports
from aliyunsdkecs.request.v20140526 import \
    CreateSecurityGroupRequest, DeleteSecurityGroupRequest, \
    AuthorizeSecurityGroupRequest, AuthorizeSecurityGroupEgressRequest, \
    JoinSecurityGroupRequest, LeaveSecurityGroupRequest, \
    DescribeSecurityGroupAttributeRequest, \
    DeleteSecurityGroupRequest

from core.base import AliyunBaseNode, AliyunBaseRelationship
from ecs import instance, constants

# Cloudify imports
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    return SecurityGroup().creation_validation()


@operation
def create(**_):
    return SecurityGroup().created()


@operation
def delete(**_):
    return SecurityGroup().deleted()


@operation
def join(**_):
    return InstanceConectToSG().associated()


@operation
def leave(**_):
    return InstanceConectToSG().disassociated()

SG_NODE_PROPERTIES = dict(
    security_group_name='SecurityGroupName'
    description='Description'
)
SG_IN_RULES_PROPERTIES_Source = dict(
    peer_group_owner_account='SourceGroupOwnerAccount',
    peer_group_id='SourceGroupId',
    ip_protocol='IpProtocol',
    #PortRange
    nic_type='NicType',
    policy='Policy'
)
SG_IN_RULES_PROPERTIES_Cidr = dict(
    peer_cidr_ip='SourceCidrIp',
    ip_protocol='IpProtocol',
    #PortRange
    nic_type='NicType'
    policy='Policy'
)
SG_OUT_RULES_PROPERTIES_SOURCE = dict(
    peer_group_owner_account='DestGroupOwnerAccount'
    peer_group_id='DestGroupId'
    ip_protocol='IpProtocol'
    #PortRange
    nic_type='NicType'
    policy='Policy'
)
SG_OUT_RULES_PROPERTIES_Cidr = dict(
    peer_cidr_ip='DestCidrIp'
    ip_protocol='IpProtocol'
    #PortRange
    nic_type='NicType'
    policy='Policy'
)
SG_IDS = 'sg_ids'


class SecurityGroup(AliyunBaseNode):

    def __init__(self, use_source_info=False):
        super(SecurityGroup, self).__init__(
            constants.SECURITY_GROUP['ALIYUN_RESOURCE_TYPE'],
            constants.SECURITY_GROUP['REQUIRED_PROPERTIES'],
            use_source_info=use_source_info
        )
        self.list_response_keys = \
            {'Items': '',  # only return 1 item or none
                'Item': '',
                'ItemId': 'SecurityGroupId',
                'TotalCount': ''}

        self._VPCid = None
        is_instance = ctx.type == constants.NODE_INSTANCE
        if not self.is_external_resource and is_instance:
            # get VPCid if contained in vpc
            vpc_instances = self.get_target_instances_of_relationship_type(
                constants.SECURITY_GROUP_VPC_RELATIONSHIP,
                ctx.instance.relationships)
            if len(vpc_instances) > 1:
                raise NonRecoverableError(
                    'security group may only be attached to one vpc')
            if len(vpc_instances) == 1:
                self._VPCid = self.get_external_resource_id(
                    vpc_instances[0])

    def get_query_resource_request(self, list_of_ids=None):
        # query detail info
        query = DescribeSecurityGroupAttributeRequest.\
            DescribeSecurityGroupAttributeRequest()
        if list_of_ids and len(list_of_ids) > 0:
            query.set_SecurityGroupId(list_of_ids[0])
        return query

    def use_external_resource_naively(self):
        # still process even external resource
        return False

    def create(self):
        # create group only when it is not existing extern resource
        if not self.is_external_resource:
            request = CreateSecurityGroupRequest.CreateSecurityGroupRequest()
            for key in SG_NODE_PROPERTIES.keys():
                if key in ctx.node.properties:
                    set_function = None
                    if len(str(ctx.node.properties[key]))>0:
                        set_function = getattr(
                            request, 'set_' + SG_NODE_PROPERTIES[key], None)
                    if set_function:
                        set_function(ctx.node.properties[key])
            if self._VPCid:
                request.set_VpcId(self._VPCid)
            lsb = self.execute(request, raise_on_falsy=True)
            self.resource_id = lsb['SecurityGroupId']
            # todo:
            #self.create_sg()
            # todo: exec CreateSecurityGroupRequest
            # use self._VPCid param if not None
        self.create_rules()
        return True

    def create_rules(self):
        sg_json = self.get_resource()
        for item in ctx.node.properties['rules']:
            self._create_rule(sg_json, item)

    def _create_rule(self, sg_json, item):
        group_rule_equallity = 0
        if 'port_range_from' in item and 'port_range_to' in item:
            port_range = str(item['port_range_from']) + '/' + str(item['port_range_to'])
        # in rules:
        if 'peer_cidr_ip' in item:
            SG_IN_RULES_PROPERTIES = SG_IN_RULES_PROPERTIES_Cidr
        else:
            if 'peer_group_id' in item:
                SG_IN_RULES_PROPERTIES = SG_IN_RULES_PROPERTIES_Source
        for key in SG_IN_RULES_PROPERTIES.keys():
            if key in item:
                continue
            else:
                group_rule_equallity = 1
        #group_rule_equallity = 1 means this rule does not exit before and can be created.
        if group_rule_equallity:
            for key, value in item.items():
                if isinstance(value, type(True)):
                    value = 'on' if value else 'off'
                if key in SG_IN_RULES_PROPERTIES.keys() and len(str(value)) >0:
                    set_function = getattr(
                        request, 'set_' + SG_IN_RULES_PROPERTIES[key], None
                    )
                    if set_function:
                        set_function(value)
            #equals to add value to setter
            #need to think about how port_range work here.
            set_function_portrange = getattr(
                request, 'set_PortRange', None)
            if set_function_portrange:
                set_function_portrange(port_range)
        # set data for out rules:
        
        # todo: create rule if it not in sg
        # in rule, ref to: https://help.aliyun.com/document_detail/25554.html
        # the following fields determine an in rule:
        # SourceGroupOwnerAccount SourceGroupId IpProtocol PortRange
        #  NicType Policy
        # SourceCidrIp IpProtocol PortRange NicType Policy

        # out rule, ref to: https://help.aliyun.com/document_detail/25560.html
        # the following fields determine an out rule:
        # DestGroupOwnerAccount DestGroupId IpProtocol PortRange
        #  NicType Policy
        # DestCidrIp IpProtocol PortRange NicType Policy

        # todo: use dynamic function call to simplify code:
        # set_function = getattr(request, set_fun_name, None)
        return True

    # set runtime properties after create
    def set_runtime_properties(self, slb):
        # no special properties to set
        pass

    def delete(self):
        deleteRequest = DeleteSecurityGroupRequest.DeleteSecurityGroupRequest()
        deleteRequest.set_SecurityGroupId(self.resource_id)
        self.execute(deleteRequest, raise_on_falsy=True)
        # todo: DeleteSecurityGroupRequest checked
        return True


class InstanceConectToSG(AliyunBaseRelationship):

    def __init__(self):
        super(InstanceConectToSG, self).__init__(
            use_source_info=False)

    def get_source_target_object(self, is_source=True):
        if is_source:
            return instance.Instance()
        else:
            return SecurityGroup()

    def associate(self):
        instance_id = self.source_resource_id
        sg_id = self.target_resource_id
        joinRequest = JoinSecurityGroupRequest.JoinSecurityGroupRequest()
        joinRequest.set_SecurityGroupId(self.resource_id)
        self.execute(joinRequest, raise_on_falsy=False)
        json_sg, sg = self.get_target_resource()
        if 'Code' in json_sg:
            raise NonRecoverableError(
                'query sg {0}, code {1}, message: {2}'.
                format(sg.resource_id,
                        json_sg['Code'],
                        json_sg['Message']
                        )
            )
        if 'Code' = InvalidInstanceId.AlreadyExists:
            return True
        # todo: call exec JoinSecurityGroupRequest with raise_on_falsy=False checked
        # if 'Code' = InvalidInstanceId.AlreadyExists, return TRUE
        # ref to: https://help.aliyun.com/document_detail/25508.html
        # if other Error, raise

        # add sg_id after join ok
        src_properties = ctx.source.instance.runtime_properties
        if SG_IDS not in src_properties:
            src_properties[SG_IDS] = [sg_id]
        else:
            src_properties[SG_IDS].append(sg_id)
        return True

    def use_source_external_resource_naively(self):
        # external_resource still try to connect
        # so we return False
        return False

    def disassociate(self):
        # disassociate only when the source has sg_id
        src_properties = ctx.source.instance.runtime_properties
        if SG_IDS not in src_properties:
            return True
        if self.target_resource_id not in src_properties[SG_IDS]:
            return True

        json_instance, instance = self.get_source_resource()
        # todo: if json_instance has only 1 sg left, return True
        # if json_instance is not Running or Stopped, return False
        # ref to: https://help.aliyun.com/document_detail/25509.html

        # todo: exec LeaveSecurityGroupRequest
        return True

    def disassociate_external_resource_naively(self):
        # external_resource still try to disconnect
        # so we return False
        return False

    def post_disassociate(self):
        # remove sg_id from source runtime_properties SG_IDS list
        src_properties = ctx.source.instance.runtime_properties
        if SG_IDS not in src_properties:
            return True
        src_properties[SG_IDS].remove(self.target_resource_id)
        return True
