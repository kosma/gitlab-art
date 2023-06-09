# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
from . import _paths
from . import _yaml


def save(gitlab_url, token_type, token):
    config = {
        'gitlab_url': gitlab_url,
        'token_type': token_type,
        'token': token,
    }
    _paths.mkdirs(os.path.dirname(_paths.config_file))
    _yaml.save(_paths.config_file, config)


def load():
    config = _yaml.load(_paths.config_file)
   
    # migrate legacy private_token to token/token_type
    if 'private_token' in config:
        config['token'] = config['private_token']
        config['token_type'] = 'private'
        del config['private_token']
        
    return config
