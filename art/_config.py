# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
from . import _paths
from . import _yaml


def save(gitlab_url, token_type, token):
    config = {
        'gitlab_url': gitlab_url,
    }
    if token_type == 'private':
        config['private_token'] = token
        config['job_token'] = None
    elif token_type == 'job':
        config['job_token'] = token
        config['private_token'] = None
    _paths.mkdirs(os.path.dirname(_paths.config_file))
    _yaml.save(_paths.config_file, config)


def load():
    return _yaml.load(_paths.config_file)
