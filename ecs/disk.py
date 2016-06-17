########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#

# Third-party Imports
# import boto.exception

# Cloudify imports
# from cloudify import ctx
# from cloudify import compute
# from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    # todo
    pass


@operation
def create(**_):
    pass


@operation
def delete(**_):
    pass


@operation
def create_snapshot(**_):
    pass


@operation
def attach(**_):
    pass


@operation
def detach(**_):
    pass
