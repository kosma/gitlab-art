# -*- coding: utf-8 -*-

import yaml


def load(path):
    with open(path, 'rb') as stream:
        return yaml.safe_load(stream=stream)


def save(path, obj):
    with open(path, 'wb') as stream:
        yaml.safe_dump(obj, stream=stream, default_flow_style=False)
