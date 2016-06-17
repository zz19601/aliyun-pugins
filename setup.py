########
# Copyright (c) 2016 Dayang Technologies Ltd. All rights reserved
#


from setuptools import setup

# Replace the place holders with values for your project

setup(

    # Do not use underscores in the plugin name.
    name='cloudify-aliyun-plugin',
    author='Dayang',
    author_email='wangyanbin@dayang.com.cn',

    version='0.1.1',
    description='Cloudify plugin for Aliyun infrastructure.',

    # This must correspond to the actual packages in the plugin.
    packages=[
        'core',
        'ecs',
        'vpc',
        'slb'
    ],

    license='LICENSE',
    install_requires=[
        'cloudify-plugins-common>=3.3.1',
        'aliyun-python-sdk-core==2.0.33',        
        'aliyun-python-sdk-ecs==2.1.0',
        'aliyun-python-sdk-slb==2.0.21'
    ]
)
