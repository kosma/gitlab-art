# -*- coding: utf-8 -*-

from __future__ import absolute_import

import re
import os
from . import _paths
from . import _yaml


def save(gitlab_url, private_token):
    config = {
        'gitlab_url': gitlab_url,
        'private_token': private_token,
    }
    _paths.mkdirs(os.path.dirname(_paths.config_file))
    _yaml.save(_paths.config_file, config)


def load():
    return _yaml.load(_paths.config_file)
