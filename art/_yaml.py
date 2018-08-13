# -*- coding: utf-8 -*-

import yaml


def load(path):
    with open(path, 'r') as stream:
        return yaml.safe_load(stream=stream)


def save(path, obj):
    with open(path, 'w') as stream:
        yaml.safe_dump(obj, stream=stream, default_flow_style=False)
