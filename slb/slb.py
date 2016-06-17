########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports
from aliyunsdkslb.request.v20160520 import (
    # DescribeLoadBalancersRequest,
    CreateLoadBalancerRequest,
    DescribeLoadBalancerAttributeRequest as DescribeSLB,
    DeleteLoadBalancerRequest,

    CreateLoadBalancerHTTPListenerRequest,
    CreateLoadBalancerHTTPSListenerRequest,
    CreateLoadBalancerTCPListenerRequest,
    CreateLoadBalancerUDPListenerRequest,
    StartLoadBalancerListenerRequest,
    # StopLoadBalancerListenerRequest,
    # DeleteLoadBalancerListenerRequest,
    DescribeLoadBalancerHTTPListenerAttributeRequest,
    DescribeLoadBalancerHTTPSListenerAttributeRequest,
    DescribeLoadBalancerTCPListenerAttributeRequest,
    DescribeLoadBalancerUDPListenerAttributeRequest,

    AddBackendServersRequest,
    RemoveBackendServersRequest,
    )


from core.base import AliyunBaseNode, AliyunBaseRelationship
from ecs import instance, constants

# Cloudify imports
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    return ServerLoadBalancer().creation_validation()


@operation
def create(**_):
    return ServerLoadBalancer().created()


@operation
def delete(**_):
    return ServerLoadBalancer().deleted()


@operation
def add_instance_to_slb(weight, vserver_group_id, vserver_group_name, **_):
    return InstanceConectToSLB(weight,
                               vserver_group_id,
                               vserver_group_name).associated()


@operation
def remove_instance_from_slb(**_):
    return InstanceConectToSLB().disassociated()


SLB_NODE_PROPERTIES = dict(
    slb_name='LoadBalancerName',
    address_type='AddressType',
    internet_charge_type='InternetChargeType',
    band_width='Bandwidth',
    master_zone_id='MasterZoneId',
    slave_zone_id='SlaveZoneId',
    )

SLB_LISTENER_PROPERTIES = dict(
    listener_port='ListenerPort',
    backend_server_port='BackendServerPort',
    band_width='Bandwidth',
    scheduler='Scheduler',
    health_check='HealthCheck',
    )
SLB_LISTENER_OTHER_PROPERTIES = [
    # http
    'XForwardedFor', 'StickySession', 'StickySessionType', 'CookieTimeout',
    'Cookie', 'HealthCheck', 'HealthCheckDomain', 'HealthCheckURI',
    'HealthyThreshold', 'UnhealthyThreshold', 'HealthCheckTimeout',
    'HealthCheckConnectPort', 'HealthCheckInterval', 'HealthCheckHttpCode',
    'MaxConnection', 'VServerGroupId', 'Tags',
    # https
    'ServerCertificateId', 'CACertificateId',
    # tcp, note, some param first letter is lower case: *healthCheckInterval
    'PersistenceTimeout', 'HealthCheckConnectTimeout',
    'HealthCheckType', 'healthCheckInterval'
    # udp, note: *healthCheckInterval, *healthCheckReq
    'healthCheckReq', 'healthCheckExp', 'HealthCheckReq'
    ]

SLB_IDS = 'slb_ids'


class ServerLoadBalancer(AliyunBaseNode):

    def __init__(self, use_source_info=False):
        super(ServerLoadBalancer, self).__init__(
            constants.SLB['ALIYUN_RESOURCE_TYPE'],
            constants.SLB['REQUIRED_PROPERTIES'],
            use_source_info=use_source_info
        )
        self.list_response_keys = \
            {'Items': '',  # only return 1 item or none
                'Item': '',
                'ItemId': 'LoadBalancerId',
                'TotalCount': ''}

        self._VSwitchid = None
        is_instance = ctx.type == constants.NODE_INSTANCE
        if not self.is_external_resource and is_instance:
            # get vSwitchID if contained in subnet
            subnet_instances = self.get_target_instances_of_relationship_type(
                constants.SLB_SUBNET_RELATIONSHIP,
                ctx.instance.relationships)
            if len(subnet_instances) > 1:
                raise NonRecoverableError(
                    'slb may only be attached to one subnet')
            if len(subnet_instances) == 1:
                self._VSwitchid = self.get_external_resource_id(
                    subnet_instances[0])

    def get_query_resource_request(self, list_of_ids=None):
        # query detail info
        query = DescribeSLB.DescribeLoadBalancerAttributeRequest()
        if list_of_ids and len(list_of_ids) > 0:
            query.set_LoadBalancerId(list_of_ids[0])
        return query

    def use_external_resource_naively(self):
        # still process even external resource
        return False

    def create(self):
        if not self.is_external_resource:
            request = CreateLoadBalancerRequest.CreateLoadBalancerRequest()
            # set node properties
            for key in SLB_NODE_PROPERTIES.keys():
                if key in ctx.node.properties:
                    set_function = None
                    if len(str(ctx.node.properties[key])) > 0:
                        set_function = getattr(
                            request, 'set_' + SLB_NODE_PROPERTIES[key], None)
                    if set_function:
                        set_function(ctx.node.properties[key])
            if self._VSwitchid:
                request.set_VSwitchId(self._VSwitchid)
            lsb = self.execute(request, raise_on_falsy=True)
            self.resource_id = lsb['LoadBalancerId']
        self.create_listeners()
        return True

    def create_listeners(self):
        for item in ctx.node.properties['listeners']:
            self._create_listener(item)

    def _create_listener(self, item):
        protocol = item['protocol']
        request, query = self._get_create_listener_request(protocol)
        request.set_LoadBalancerId(self.resource_id)
        query.set_LoadBalancerId(self.resource_id)
        listener_port = item['listener_port']
        query.set_ListenerPort(listener_port)
        status = None
        for key, value in item.items():
            # bool to on/off
            if isinstance(value, type(True)):
                value = 'on' if value else 'off'
            # ctx.logger.info('key:{0},value:{1}'.format(key, value))
            if key in SLB_LISTENER_PROPERTIES.keys() and len(str(value)) > 0:
                set_function = getattr(
                    request, 'set_' + SLB_LISTENER_PROPERTIES[key], None)
                if set_function:
                    set_function(value)

        if 'others' in item:
            for key, value in item['others'].items():
                if key == 'protocol':
                    continue
                set_function = None
                if isinstance(value, type(True)):
                    value = 'on' if value else 'off'
                if len(str(value)) > 0:
                    set_function = getattr(
                        request, 'set_' + key, None)
                    # special for some lower case param: healthCheckExp
                    if not set_function and key[0].isupper():
                        set_function = getattr(
                            request, 'set_' + key[0].lower() + key[1:], None)
                if set_function:
                    set_function(value)
        create = True
        # if extern, only create if not exist
        if self.is_external_resource:
            create = False
            # first query, no need use copy
            response = self.execute(query, raise_on_falsy=False)
            if 'Code' in response:
                if response['Code'] == 'InvalidParameter':
                    create = True
                else:
                    raise NonRecoverableError(
                        'Request {0} returned error, Code:{1}, Msg:{2}.'
                        .format(request,
                                response['Code'],
                                response['Message']))
            else:
                status = response['Status']
        # create it
        if create:
            self.execute(request, raise_on_falsy=True)
        # query status, if stopped start it
        if not status:
            # query again
            # if not use new object, will return IncompleteSignature
            query = self._get_new_query_listener_request(query)
            response = self.execute(query, raise_on_falsy=True)
            status = response['Status']
        if status == 'stopped':
            start = StartLoadBalancerListenerRequest.\
                StartLoadBalancerListenerRequest()
            start.set_LoadBalancerId(self.resource_id)
            start.set_ListenerPort(listener_port)
            response = self.execute(start, raise_on_falsy=True)
            # if not use new object, will return IncompleteSignature
            query = self._get_new_query_listener_request(query)
            response = self.execute(query, raise_on_falsy=True)
            status = response['Status']
        ctx.logger.info(
                'slb listener port {0}, status {1}.'
                .format(listener_port, status))

    def _get_new_query_listener_request(self, query):
        request = query.__class__()
        request.set_LoadBalancerId(query.get_LoadBalancerId())
        request.set_ListenerPort(query.get_ListenerPort())
        return request

    def _get_create_listener_request(self, protocol):
        request = CreateLoadBalancerTCPListenerRequest.\
            CreateLoadBalancerTCPListenerRequest()
        query = DescribeLoadBalancerTCPListenerAttributeRequest.\
            DescribeLoadBalancerTCPListenerAttributeRequest()
        protocol = protocol.lower()
        if protocol == 'http':
            request = CreateLoadBalancerHTTPListenerRequest.\
                CreateLoadBalancerHTTPListenerRequest()
            query = DescribeLoadBalancerHTTPListenerAttributeRequest.\
                DescribeLoadBalancerHTTPListenerAttributeRequest()
        elif protocol == 'https':
            request = CreateLoadBalancerHTTPSListenerRequest.\
                CreateLoadBalancerHTTPSListenerRequest()
            query = DescribeLoadBalancerHTTPSListenerAttributeRequest.\
                DescribeLoadBalancerHTTPSListenerAttributeRequest()
        elif protocol == 'udp':
            request = CreateLoadBalancerUDPListenerRequest.\
                CreateLoadBalancerUDPListenerRequest()
            query = DescribeLoadBalancerUDPListenerAttributeRequest.\
                DescribeLoadBalancerUDPListenerAttributeRequest()
        return request, query

    def set_runtime_properties(self, slb):
        # slb_ip
        ctx.instance.runtime_properties['slb_ip'] = slb['Address']

    def delete(self):
        delereRequest = DeleteLoadBalancerRequest.DeleteLoadBalancerRequest()
        delereRequest.set_LoadBalancerId(self.resource_id)
        self.execute(delereRequest, raise_on_falsy=True)
        return True


class InstanceConectToSLB(AliyunBaseRelationship):

    def __init__(self, weight=100, vserver_group_id='', vserver_group_name=''):
        super(InstanceConectToSLB, self).__init__(
            use_source_info=False)
        self._weight = weight
        self._vserver_group_id = vserver_group_id
        self._vserver_group_name = vserver_group_name

    def get_source_target_object(self, is_source=True):
        if is_source:
            return instance.Instance()
        else:
            return ServerLoadBalancer()

    def associate(self):
        json_slb, slb = self.get_target_resource()
        # check if instance exist
        if 'Code' in json_slb:
            raise NonRecoverableError(
                'query slb {0}, code:{1}, message:{2}'.
                format(slb.resource_id,
                       json_slb['Code'],
                       json_slb['Message']
                       ))
        for server in json_slb['BackendServers']['BackendServer']:
            if server['ServerId'] == self.source_resource_id:
                ctx.logger.info('{0} already added to slb {1}.'
                                .format(self.source_resource_id,
                                        self.target_resource_id))
                return True
        json_instance, instance = self.get_source_resource()
        if json_instance['Status'] != 'Running':
            raise NonRecoverableError(
                'instance in {0} status, cannot associate slb'.
                format(json_instance['Status']))
        is_ok = self.add_server(slb.resource_id, instance.resource_id)
        return is_ok

    def use_source_external_resource_naively(self):
        # external_resource still try to connect
        # so we return False
        return False

    def disassociate(self):
        # disassociate only when the source has slb_id
        src_properties = ctx.source.instance.runtime_properties
        if SLB_IDS not in src_properties:
            return True
        if self.target_resource_id not in src_properties[SLB_IDS]:
            return True
        return self.remove_server(self.target_resource_id,
                                  self.source_resource_id)

    def disassociate_external_resource_naively(self):
        # external_resource still try to disconnect
        # so we return False
        return False

    def add_server(self, slb_id, instance_id):
        request = AddBackendServersRequest.AddBackendServersRequest()
        request.set_LoadBalancerId(slb_id)
        # BackendServers=[{"ServerId":" vm-233","Weight":"100"},
        # {"ServerId":" vm-234","Weight":"100"}]
        server = {}
        server['ServerId'] = instance_id
        server['Weight'] = self._weight
        servers = [server]
        str_servers = str(servers)
        ctx.logger.info('BackendServers:{0}'.format(str_servers))
        request.set_BackendServers(str_servers)
        self.execute(request, raise_on_falsy=True)
        src_properties = ctx.source.instance.runtime_properties
        if SLB_IDS not in src_properties:
            src_properties[SLB_IDS] = [slb_id]
        else:
            src_properties[SLB_IDS].append(slb_id)
        return True

    def remove_server(self, slb_id, instance_id):
        request = RemoveBackendServersRequest.RemoveBackendServersRequest()
        request.set_LoadBalancerId(slb_id)
        servers = [instance_id]
        request.set_BackendServers(str(servers))
        self.execute(request, raise_on_falsy=True)
        return True

    def post_disassociate(self):
        src_properties = ctx.source.instance.runtime_properties
        if SLB_IDS not in src_properties:
            return True
        src_properties[SLB_IDS].remove(self.target_resource_id)
        return True
