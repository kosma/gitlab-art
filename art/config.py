# -*- coding: utf-8 -*-

import appdirs
import errno
import os
import yaml


_appdir = appdirs.user_config_dir('art')
_config_file = os.path.join(_appdir, 'config.yml')


def _create_appdir():
    try:
        os.mkdir(_appdir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def save(gitlab_url, private_token):
    _create_appdir()
    config = {
        'gitlab_url': gitlab_url,
        'auth_header': {'PRIVATE-TOKEN': private_token}
    }
    with open(_config_file, 'wb') as stream:
        yaml.safe_dump(config, stream=stream)


def load():
    with open(_config_file, 'rb') as stream:
        return yaml.safe_load(stream=stream)


def guess_from_env():
    if 'GITLAB_CI' in os.environ:
        # we have to jump through some hoops to get the API URL
        build_token = os.environ['CI_BUILD_TOKEN']
        project_url = os.environ['CI_PROJECT_URL']
        project_path = os.environ['CI_PROJECT_PATH']
        if not project_url.endswith(project_path):
            raise ValueError("%r doesn't end with %r" % (ci_project_name, ci_project_path))
        gitlab_url = project_url[:-len(project_path)]
        # the rest is simple
        config = {
            'gitlab_url': gitlab_url,
            'auth_header': {'BUILD-TOKEN': build_token}
        }
        return config
    else:
        return None
