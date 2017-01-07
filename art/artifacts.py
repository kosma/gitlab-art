# -*- coding: utf-8 -*-

import yaml


_artifacts_file = 'artifacts.yml'
_artifacts_lock_file = 'artifacts.lock.yml'

def load():
    with open(_artifacts_file, 'rb') as stream:
        return yaml.safe_load(stream=stream)

def save(artifacts_lock):
    with open(_artifacts_lock_file, 'wb') as stream:
        return yaml.safe_dump(artifacts_lock, stream=stream, default_flow_style=False)
