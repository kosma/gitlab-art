# -*- coding: utf-8 -*-

import click
import yaml


def load(path):
    try:
        with open(path, 'r') as stream:
            return yaml.safe_load(stream=stream)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise click.ClickException('Failed to read file: %s' % exc)

def save(path, obj):
    try:
        with open(path, 'w') as stream:
            yaml.safe_dump(obj, stream=stream, default_flow_style=False)
    except OSError as exc:
        raise click.ClickException('Failed to write file: %s' % exc)
