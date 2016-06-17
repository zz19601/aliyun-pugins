#########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports
from aliyunsdkcore.acs_exception.exceptions import \
    ClientException, ServerException
import json

# inner import
from ecs import utils as ecs_utils
from ecs import constants, connection

# Cloudify imports
from cloudify.exceptions import NonRecoverableError  # RecoverableError
from cloudify import ctx


class AliyunBase(object):

    def __init__(self,
                 client=None,
                 use_source_info=True
                 ):
        self.client = client if client \
            else connection.Client(use_source_info).client()
        self.list_response_keys = {'Items': '',
                                   'Item': '',
                                   'ItemId': '',
                                   'TotalCount': ''}

    # return response of json object
    def execute(self, request, raise_on_falsy=False):
        jsonobj = None
        try:
            request.set_accept_format('json')
            result = self.client.do_action(request)
            if result:
                jsonobj = json.loads(result)
        except (ClientException,
                ServerException, ValueError) as e:
            raise NonRecoverableError('{0}'.format(str(e)))

        if raise_on_falsy and not jsonobj:
            raise NonRecoverableError(
                'Request {0} returned False.'.format(request))
        if raise_on_falsy and ('Code' in jsonobj):
            raise NonRecoverableError(
                'Request {0} returned error, Code:{1}, Msg:{2}.'
                .format(request, jsonobj['Code'], jsonobj['Message']))
        return jsonobj

    def get_and_filter_resources_by_matcher(
            self, filter_query_request):
        try:
            filter_query_request.set_accept_format('json')
            result = self.client.do_action(filter_query_request)
            json_result = []
            if result:
                json_result = json.loads(result)
            totals = self.list_response_keys['TotalCount']
            items = self.list_response_keys['Items']
            item = self.list_response_keys['Item']
            if totals in json_result:
                if json_result[totals] == 0:
                    return []
            if len(items) > 0 and items not in json_result:
                raise NonRecoverableError(
                        'result no {0}:{1}'.format(
                            items, json_result))
            if len(items) > 0 and item not in json_result[items]:
                raise NonRecoverableError(
                        'result no {0}'.format(item))
            if len(items) > 0 and len(item) > 0:
                return json_result[items][item]
            else:
                return [json_result]
        except (ClientException,
                ServerException, ValueError) as e:
            raise NonRecoverableError('{0}'.format(str(e)))

    def filter_for_single_resource(self, filter_query_request, resource_id):

        resources = self.\
            get_and_filter_resources_by_matcher(filter_query_request)
        if resources:
            for resource in resources:
                itemid = self.list_response_keys['ItemId']
                # simple support for 'a.b.c'
                # such as 'PublicIpAddress.IpAddress'
                item_ids = itemid.split('.')
                index = 0
                for item in item_ids:
                    index += 1
                    if item not in resource:
                        break
                    if len(item_ids) == index:
                        # may be list of ids
                        # such as "IpAddress": ["123.57.1.1"]
                        if isinstance(resource[item], type([])):
                            for id in resource[item]:
                                if id == resource_id:
                                    return resource
                        else:
                            if resource[item] == resource_id:
                                return resource
                    resource = resource[item]

        return None

    def get_related_targets_and_types(self, relationships):
        """

        :param relationships: should be ctx.instance.relationships
        or ctx.source/target.instance.relationships
        :return: targets_and_types a dict of structure
        relationship-type: relationship_target_id
        """

        targets_by_relationship_type = dict()

        if len(relationships) > 0:

            for relationship in relationships:
                targets_by_relationship_type.update(
                    {
                        relationship.type:
                            relationship.target.instance
                            .runtime_properties.get(
                                constants.EXTERNAL_RESOURCE_ID)
                    }
                )

        return targets_by_relationship_type

    def get_target_instances_of_relationship_type(
            self, relationship_type,
            relationships):
        target_instances = []
        for relationship in relationships:
            if relationship_type in relationship.type:
                target_instances.append(relationship.target.instance)
        return target_instances

    def get_external_resource_id(self, instance):
        return instance.runtime_properties.get(constants.EXTERNAL_RESOURCE_ID)

    def get_target_ids_of_relationship_type(
            self, relationship_type,
            targets_by_relationship_type):

        target_ids = []

        for current_relationship_type, current_target_id in \
                targets_by_relationship_type.items():

            if relationship_type in current_relationship_type:
                target_ids.append(current_target_id)

        return target_ids

    def raise_forbidden_external_resource(self, resource_id):
        raise NonRecoverableError(
            'Cannot use_external_resource because resource {0} '
            'is not in this account.'.format(resource_id))


# this class is used in cloudify context
class AliyunBaseRelationship(AliyunBase):

    def __init__(self, client=None, use_source_info=True):
        super(AliyunBaseRelationship, self).__init__(client, use_source_info)
        self.source_resource_id = \
            ctx.source.instance.runtime_properties.get(
                constants.EXTERNAL_RESOURCE_ID, None) if \
            constants.EXTERNAL_RESOURCE_ID in \
            ctx.source.instance.runtime_properties.keys() else \
            ctx.source.node.properties['resource_id']
        self.target_resource_id = ctx.target.instance.runtime_properties.get(
            constants.EXTERNAL_RESOURCE_ID, None) if \
            constants.EXTERNAL_RESOURCE_ID in \
            ctx.target.instance.runtime_properties.keys() else \
            ctx.target.node.properties['resource_id']
        self.source_is_external_resource = \
            ctx.source.node.properties['use_external_resource']

    def associate(self):
        return False

    def associated(self):

        ctx.logger.info(
            'Attempting to associate {0} with {1}.'
            .format(self.source_resource_id,
                    self.target_resource_id))

        if self.use_source_external_resource_naively() \
                or self.associate():
            return self.post_associate()

        self.raise_associated_error()

    def is_associate_ready(self):
        # implement in subclass
        return True

    def raise_associated_error(self, disassociate=False):
        raise NonRecoverableError(
            'Source is neither external resource, '
            'nor Cloudify resource, unable to {0}associate {1} {2} {3}.'
            .format('dis' if disassociate else '',
                    self.source_resource_id,
                    'from' if disassociate else 'with',
                    self.target_resource_id))

    def associated_async(self, retry_after=3):

        ctx.logger.info(
            'Attempting to associate {0} with {1}.'
            .format(self.source_resource_id,
                    self.target_resource_id))

        if ctx.operation.retry_number == 0:
            is_ok = self.use_source_external_resource_naively() \
                or self.associate()
            if not is_ok:
                self.raise_associated_error()

        if self.is_associate_ready():
            is_ok = self.post_associate()
        else:
            return ctx.operation.retry(
                message='Still wait associating {0} with {1} ready...'
                        .format(self.source_resource_id,
                                self.target_resource_id),
                retry_after=retry_after)

        if not is_ok:
            self.raise_associated_error()

        return True

    def use_source_external_resource_naively(self):

        if not self.source_is_external_resource:
            return False

        resource, src = self.get_source_resource()

        if resource is None:
            self.raise_forbidden_external_resource(
                self.source_resource_id)

        ctx.logger.info(
            'Assuming {0} is external, because the user '
            'specified use_external_resource. Not associating it with {1}.'
            .format(resource.id, self.target_resource_id))

        return True

    def disassociate(self):
        return False

    def disassociated(self):

        ctx.logger.info(
            'Attempting to disassociate {0} from {1}.'
            .format(self.source_resource_id, self.target_resource_id))

        if self.disassociate_external_resource_naively() \
                or self.disassociate():
            return self.post_disassociate()

        self.raise_associated_error(disassociate=True)

    def disassociated_async(self, retry_after=3):
        ctx.logger.info(
            'Attempting to disassociate {0} from {1}.'
            .format(self.source_resource_id, self.target_resource_id))

        if ctx.operation.retry_number == 0:
            is_ok = self.disassociate_external_resource_naively() \
                or self.disassociate()
            if not is_ok:
                self.raise_associated_error(disassociate=True)

        if self.is_disassociate_ready():
            is_ok = self.post_disassociate()
        else:
            return ctx.operation.retry(
                message='Still wait disassociating {0} from {1} finished...'
                        .format(self.source_resource_id,
                                self.target_resource_id),
                retry_after=retry_after)

        if not is_ok:
            self.raise_associated_error(disassociate=True)

        return True

    def disassociate_external_resource_naively(self):

        if not self.source_is_external_resource:
            return False

        resource = self.get_source_resource()

        ctx.logger.info(
            'Assuming {0} is external, because the user '
            'specified use_external_resource. Not disassociating it with {1}.'
            .format(resource.id, self.target_resource_id))

        return True

    def post_associate(self):
        return True

    def post_disassociate(self):
        return True

    def get_source_target_object(self, is_source=True):
        raise NonRecoverableError('not implement')

    def get_source_resource(self):
        source = self.get_source_target_object()
        # no need set it?
        source.resource_id = self.source_resource_id
        resource = source.get_resource()
        return resource, source

    def get_target_resource(self):
        target = self.get_source_target_object(is_source=False)
        # no need set it?
        target.resource_id = self.target_resource_id
        resource = target.get_resource()
        return resource, target


# this class is used in cloudify context
class AliyunBaseNode(AliyunBase):

    def __init__(self,
                 aliyun_resource_type,
                 required_properties,
                 client=None,
                 use_source_info=True
                 ):
        super(AliyunBaseNode, self).__init__(client, use_source_info)

        self.aliyun_resource_type = aliyun_resource_type
        # when ctx is relationship, use the info of source or target
        # note: self._instance and self._node only used in __init__
        if ctx.type == constants.RELATIONSHIP_INSTANCE:
            if use_source_info:
                self._instance = ctx.source.instance
                self._node = ctx.source.node
            else:
                self._instance = ctx.target.instance
                self._node = ctx.target.node
        elif ctx.type == constants.NODE_INSTANCE:
            self._instance = ctx.instance
            self._node = ctx.node
        self.cloudify_node_instance_id = self._instance.id
        self.resource_id = \
            self._instance.runtime_properties.get(
                constants.EXTERNAL_RESOURCE_ID, None) if \
            constants.EXTERNAL_RESOURCE_ID in \
            self._instance.runtime_properties.keys() else \
            self._node.properties['resource_id']
        self.is_external_resource = \
            self._node.properties['use_external_resource']
        self.required_properties = required_properties
        self.create_ready_status = ['Available']

    def creation_validation(self):
        """ This validates all VPC Nodes before bootstrap.
        """

        resource = self.get_resource()

        for property_key in self.required_properties:
            ecs_utils.validate_node_property(
                property_key, ctx.node.properties)

        if self.is_external_resource and not resource:
            raise NonRecoverableError(
                'External resource, but the supplied {0} '
                'does not exist in the account.'
                .format(self.aliyun_resource_type))

        if not self.is_external_resource and resource:
            raise NonRecoverableError(
                'Not external resource, but the supplied {0}'
                'exists in the account.'
                .format(self.aliyun_resource_type))

    def create(self):
        return False

    def is_create_ready(self):
        resource = self.get_resource()
        ready = resource and resource['Status'] in self.create_ready_status
        return ready

    def set_runtime_properties(self, resource):
        pass

    def created(self):

        ctx.logger.info(
            'Attempting to create {0} {1}.'
            .format(self.aliyun_resource_type,
                    self.cloudify_node_instance_id))

        if self.use_external_resource_naively() or self.create():
            return self.post_create()

        raise NonRecoverableError(
            'Neither external resource, nor Cloudify resource, '
            'unable to create this resource.')

    def created_async(self, retry_after=5):

        ctx.logger.info(
            'Attempting to async create {0} {1}.'
            .format(self.aliyun_resource_type,
                    self.cloudify_node_instance_id))

        is_extern = self.use_external_resource_naively()
        if not is_extern:
            if ctx.operation.retry_number == 0:
                if not self.create():
                    raise NonRecoverableError(
                        'Neither external resource, nor Cloudify resource, '
                        'unable to create this resource.')
                # set external ID, for query status in next try
                ecs_utils.set_external_resource_id(self.resource_id,
                                                   ctx.instance, False)

        if self.is_create_ready():
            return self.post_create()
        else:
            return ctx.operation.retry(
                message='Still waiting for {0} {1} to ready...'
                        .format(self.aliyun_resource_type,
                                self.cloudify_node_instance_id),
                retry_after=retry_after)

    def use_external_resource_naively(self):

        if not self.is_external_resource:
            return False

        if not self.get_resource():
            self.raise_forbidden_external_resource(self.resource_id)

        ctx.logger.info(
            'Assuming {0} is external, because the user '
            'specified use_external_resource. Not creating it.'
            .format(self.aliyun_resource_type))

        return True

    def delete(self):
        return False

    def deleted(self):

        ctx.logger.info(
            'Attempting to delete {0} {1}.'
            .format(self.aliyun_resource_type,
                    self.cloudify_node_instance_id))

        if not self.get_resource():
            self.raise_forbidden_external_resource(self.resource_id)

        if self.delete_external_resource_naively() or self.delete():
            return self.post_delete()

        raise NonRecoverableError(
            'Neither external resource, nor Cloudify resource, '
            'unable to delete this resource.')

    def delete_external_resource_naively(self):

        if not self.is_external_resource:
            return False

        ctx.logger.info(
            'Assuming {0} is external, because the user '
            'specified use_external_resource. Not deleting {0}.'
            .format(self.aliyun_resource_type,
                    self.resource_id))

        return True

    def get_all_matching(self, list_of_ids=None):
        request = self.get_query_resource_request(list_of_ids)
        matches = self.get_and_filter_resources_by_matcher(request)
        return matches

    def get_query_resource_request(self, list_of_ids=None):
        raise NonRecoverableError('Not implement')
        # note:must implement in sub class

    def get_resource(self):
        request = self.get_query_resource_request([self.resource_id])
        resource = self.filter_for_single_resource(request, self.resource_id)
        return resource

    def post_create(self):

        ecs_utils.set_external_resource_id(self.resource_id, ctx.instance,
                                           self.is_external_resource)
        self.set_runtime_properties(self.get_resource())

        ctx.logger.info(
            'Added {0} {1} to Cloudify.'
            .format(self.aliyun_resource_type, self.resource_id))

        return True

    def post_delete(self):

        ecs_utils.unassign_runtime_property_from_resource(
            constants.EXTERNAL_RESOURCE_ID, ctx.instance)

        ctx.logger.info(
            'Removed {0} {1} from Cloudify.'
            .format(self.aliyun_resource_type, self.resource_id))

        return True
