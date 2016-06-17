########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports
from aliyunsdkecs.request.v20140526 import \
    DescribeEipAddressesRequest, AllocateEipAddressRequest, \
    AssociateEipAddressRequest, AllocatePublicIpAddressRequest as PublicIp, \
    UnassociateEipAddressRequest, ReleaseEipAddressRequest, \
    DescribeInstancesRequest

from core.base import AliyunBaseNode, AliyunBaseRelationship
from . import constants, utils, instance

# Cloudify imports
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    return ElasticIP().creation_validation()


@operation
def allocate(**_):
    return ElasticIP().created()


@operation
def release(**_):
    return ElasticIP().deleted()


@operation
def associate(**_):
    return InstanceConectToElasticIP().associated_async()


@operation
def disassociate(**_):
    return InstanceConectToElasticIP().disassociated_async()


def set_eip_runtime_properties(instance, ip_address):
    instance.runtime_properties['public_ip'] = ip_address
    instance.runtime_properties['elastic_ip'] = ip_address


class ElasticIP(AliyunBaseNode):

    def __init__(self, use_source_info=False):
        super(ElasticIP, self).__init__(
            constants.ELASTICIP['ALIYUN_RESOURCE_TYPE'],
            constants.ELASTICIP['REQUIRED_PROPERTIES'],
            use_source_info=use_source_info
        )

        self._of_vpc = True
        properties = utils.get_instance_or_source_node_properties(False)
        if properties['domain'] != 'VPC':
            # query instance using PublicIpAddresses
            # ip address is its resource id
            self._of_vpc = False
            self.list_response_keys = \
                {'Items': 'Instances',
                    'Item': 'Instance',
                    # IpAddress list
                    'ItemId': 'PublicIpAddress.IpAddress',
                    'TotalCount': 'TotalCount'}
        else:
            self.list_response_keys = \
                {'Items': 'EipAddresses',
                    'Item': 'EipAddress',
                    'ItemId': 'AllocationId',
                    'TotalCount': 'TotalCount'}

    def get_query_resource_request(self, list_of_ids=None):
        query = None
        if self._of_vpc:
            query = DescribeEipAddressesRequest.DescribeEipAddressesRequest()
            if list_of_ids and len(list_of_ids) > 0:
                query.set_AllocationId(list_of_ids[0])
        else:
            query = DescribeInstancesRequest.DescribeInstancesRequest()
            if list_of_ids and len(list_of_ids) > 0:
                query.set_InstanceNetworkType('classic')
                query.set_PublicIpAddresses(str(list_of_ids))
        return query

    def is_create_ready(self):
        return True if not self._of_vpc \
            else super(ElasticIP, self).is_create_ready()

    def created(self):
        return self.create_classic() if not self._of_vpc \
            else super(ElasticIP, self).created()

    def deleted(self):
        return True if not self._of_vpc \
            else super(ElasticIP, self).deleted()

    def create(self):
        if not self._of_vpc:  # should not vpc
            return self.create_classic()

        request = AllocateEipAddressRequest.AllocateEipAddressRequest()
        request.set_Bandwidth(ctx.node.properties['band_width'])
        request.set_InternetChargeType(
            ctx.node.properties['internet_charge_type'])
        eip = self.execute(request, raise_on_falsy=True)
        self.resource_id = eip['AllocationId']
        return True

    def set_runtime_properties(self, eip):
        if not self._of_vpc or not eip:
            return
        set_eip_runtime_properties(ctx.instance, eip['IpAddress'])

    def create_classic(self):
        # must has instance create first,
        # so we process in InstanceConectToElasticIP
        return True

    def delete(self):
        if not self._of_vpc:
            return True
        # get status
        eip = self.get_resource()
        ready = eip and eip['Status'] in self.create_ready_status
        if not ready:
            raise NonRecoverableError(
                'eip status is not Available, cannot release')
        delereRequest = ReleaseEipAddressRequest.ReleaseEipAddressRequest()
        delereRequest.set_AllocationId(self.resource_id)
        self.execute(delereRequest, raise_on_falsy=True)
        return True


# process operation of instance_connected_to_elastic_ip
class InstanceConectToElasticIP(AliyunBaseRelationship):

    def __init__(self):
        super(InstanceConectToElasticIP, self).__init__(
            use_source_info=False)
        self._of_vpc = ctx.target.node.properties['domain'] == 'VPC'

    def get_source_target_object(self, is_source=True):
        if is_source:
            return instance.Instance()
        else:
            return ElasticIP()

    def is_associate_ready(self):
        if not self._of_vpc:
            return True
        json_eip, eip = self.get_target_resource()
        return json_eip['Status'] == 'InUse'

    def is_disassociate_ready(self):
        if not self._of_vpc:
            return True
        json_eip, eip = self.get_target_resource()
        return json_eip['Status'] in eip.create_ready_status

    def associate(self):
        if not self._of_vpc:
            return self.associate_classic()

        json_instance, instance = self.get_source_resource()
        if json_instance['Status'] not in instance.create_ready_status:
            raise NonRecoverableError(
                'instance in {0} status, cannot associate eip'.
                format(json_instance['Status']))

        json_eip, eip = self.get_target_resource()
        if json_eip['Status'] not in eip.create_ready_status:
            same_id = json_eip['InstanceId'] == instance.resource_id
            if json_eip['Status'] == 'InUse' and same_id:
                # already connected by extern?
                # will not disassociate in cloudify
                return True
            raise NonRecoverableError(
                'eip in {0} status, cannot associate instance'.
                format(eip['Status']))

        is_ok = self.associate_eip(eip.resource_id, instance.resource_id)
        return is_ok

    def associate_classic(self):
        # process classic network public ip
        json_instance, instance = self.get_source_resource()
        if json_instance['InstanceNetworkType'] != 'classic':
            raise NonRecoverableError(
                'instance is of vpc network,'
                ' cannot associate public ip, should use eip')

        if json_instance['Status'] not in instance.create_ready_status:
            raise NonRecoverableError(
                'instance in {0} status, cannot associate public ip'.
                format(json_instance['Status']))

        is_ok = self.associate_public_ip(instance.resource_id)
        return is_ok

    def disassociate_classic(self):
        # no need disassociate in classic network
        ctx.logger.info('disassociate classic, no need process')
        return True

    def use_source_external_resource_naively(self):
        # external_resource still try to connect
        # so we return False
        return False

    def disassociate(self):
        if not self._of_vpc:
            return self.disassociate_classic()

        # disassociate only when the target has instance_id
        if 'instance_id' not in ctx.target.instance.runtime_properties:
            return True

        json_instance, instance = self.get_source_resource()
        if json_instance['Status'] not in instance.create_ready_status:
            raise NonRecoverableError(
                'instance in {0} status, cannot disassociate eip'.
                format(json_instance['Status']))

        json_eip, eip = self.get_target_resource()
        if json_eip['Status'] == 'Available':
            ctx.logger.info('eip {0} is already disassociated'
                            .format(eip.resource_id))
            return True

        if json_eip['Status'] == 'InUse' \
                and json_eip['InstanceId'] == instance.resource_id:
                    return self.unassociate_eip(
                        eip.resource_id, instance.resource_id)

        # may be Associating status
        raise NonRecoverableError(
            'eip in {0} status, with instance {1}, '
            ' cannot associate to {2}'
            .format(json_eip['Status'],
                    json_eip['InstanceId'],
                    instance.resource_id))

    def disassociate_external_resource_naively(self):
        # external_resource still try to disconnect
        # so we return False
        return False

    def associate_eip(self, allocation_id, instance_id,
                      instance_type='EcsInstance'):
        request = AssociateEipAddressRequest.AssociateEipAddressRequest()
        request.set_AllocationId(allocation_id)
        request.set_InstanceId(instance_id)
        request.set_InstanceType(instance_type)
        self.execute(request, raise_on_falsy=True)
        # 'instance_id' marks as associate established in cloudify
        ctx.target.instance.runtime_properties['instance_id'] = \
            instance_id
        return True

    def unassociate_eip(self, allocation_id, instance_id,
                        instance_type='EcsInstance'):
        request = UnassociateEipAddressRequest.UnassociateEipAddressRequest()
        request.set_AllocationId(allocation_id)
        request.set_InstanceId(instance_id)
        request.set_InstanceType(instance_type)
        self.execute(request, raise_on_falsy=True)
        return True

    def associate_public_ip(self, instance_id):
        request = PublicIp.AllocatePublicIpAddressRequest()
        request.set_InstanceId(instance_id)
        response = self.execute(request, raise_on_falsy=True)
        ip_address = response['IpAddress']
        utils.set_external_resource_id(ip_address, ctx.target.instance, False)
        set_eip_runtime_properties(ctx.target.instance, ip_address)
        return True

    def post_disassociate(self):
        utils.unassign_runtime_property_from_resource(
            'instance_id', ctx.target.instance)
        return True
