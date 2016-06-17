########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#


# Builtin Imports
import os
import os.path
import ConfigParser

# Third-party Imports
from aliyunsdkcore import client

# Cloudify Imports
from ecs import utils
from ecs import constants
# from cloudify.exceptions import NonRecoverableError


class Client():
    """Provides functions for getting the ECS Client
    """

    def __init__(self, use_source_info=True):
        self._client = client.AcsClient('ak', 'secret', 'cn-beijing')
        self._use_source_info = use_source_info

    def client(self):
        """Represents the aliyunsdkcore.AcsClient
        """

        aliyun_config_property = self._get_aliyun_config_property()
        # complement params if necessary
        aliyun_config_property = self._get_aliyun_config_from_file(
                        aliyun_config_property)
        # process partial property, first use from node property
        if not aliyun_config_property:
            # in current, will always return a config
            return self._client
        self._client.set_region_id(aliyun_config_property['region'])
        key = aliyun_config_property['aliyun_access_key_id']
        self._client.set_access_key(key)
        secret = aliyun_config_property['aliyun_access_key_secret']
        self._client.set_access_secret(secret)
        return self._client

    def _get_aliyun_config_property(self):
        node_properties = \
            utils.get_instance_or_source_node_properties(self._use_source_info)
        return node_properties[constants.ALIYUN_CONFIG_PROPERTY]

    def _get_aliyun_config_from_file(self, aliyun_config_property):
        """Get aliyun config from a aliyuncli cfg file
        """
        config_path = self._get_aliyun_config_file_path()
        return self._parse_config_file(config_path, aliyun_config_property)\
            if config_path else aliyun_config_property

    def _get_aliyun_config_file_path(self):
        """Get aliyun config file path from environment
        """
        path = os.environ.get(constants.ALIYUN_CONFIG_PATH_ENV_VAR_NAME)
        if not path:
            path = constants.ALIYUN_DEFAULT_CONFIG_PATH
        return os.path.expanduser(path)

    def _parse_config_file(self, path, aliyun_config_property):
        """Parse the cfg file
        """
        config = aliyun_config_property if aliyun_config_property\
            else {'region': '',
                  'aliyun_access_key_secret': '',
                  'aliyun_access_key_id': ''}
        parser = ConfigParser.ConfigParser()
        regionConfig = os.path.join(str(path), 'configure')
        keyConfig = os.path.join(str(path), 'credentials')
        config_schema = constants.ALIYUNCLI_CONFIG_SCHEMA
        for file in [regionConfig, keyConfig]:
            if os.path.isfile(file):
                parser.read(file)
                for section in parser.sections():
                    if section not in config_schema:
                        continue
                    allowed_opt_list = config_schema[section]
                    for opt, value in parser.items(section):
                        if opt in allowed_opt_list:
                            # not overwrite existing value
                            if opt not in config or len(config[opt]) == 0:
                                config[opt] = value
        return config
