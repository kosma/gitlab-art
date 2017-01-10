# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
from . import _paths
from . import _yaml


def save(gitlab_url, private_token):
    config = {
        'gitlab_url': gitlab_url,
        'auth_header': {'PRIVATE-TOKEN': private_token}
    }
    _paths.mkdirs(os.path.dirname(_paths.config_file))
    _yaml.save(_paths.config_file, config)


def load():
    return _yaml.load(_paths.config_file)


def guess_from_env():
    """
    Attempt to derive Gitlab API credentials from CI environment. Requires
    GitLab 8.12 or newer.

    """
    if 'GITLAB_CI' in os.environ:
        # we have to jump through some hoops to get the API URL
        build_token = os.environ['CI_BUILD_TOKEN']
        project_url = os.environ['CI_PROJECT_URL']
        project_path = os.environ['CI_PROJECT_PATH']
        if not project_url.endswith(project_path):
            raise ValueError("%r doesn't end with %r" % (project_url, project_path))
        gitlab_url = project_url[:-len(project_path)]
        # the rest is simple
        config = {
            'gitlab_url': gitlab_url,
            'auth_header': {'BUILD-TOKEN': build_token}
        }
        return config
    else:
        return None
