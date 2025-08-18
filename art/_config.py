# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os

import click

from . import _oauth
from . import _paths
from . import _yaml

class ConfigException(click.ClickException):
    """An exception caused by invalid configuration settings."""
    def __init__(self, config_key, message):
        msg = 'config.{}: {}'.format(config_key, message)
        super().__init__(msg)

def save(gitlab_url, token_type, token_or_client_id):
    config = {
            "gitlab_url": gitlab_url,
            "token_type": token_type,
        }
    if token_type == 'oauth':
        config['oauth_client_id'] = token_or_client_id
        config['token'], config['refresh_token'] = _oauth.authorize(gitlab_url, token_or_client_id)
    else:
        config['token'] = token_or_client_id

    write(config)

def load():
    config = _yaml.load(_paths.config_file)

    if not config:
        raise click.ClickException('No configuration found. Run "art configure" first.')

    # convert old config to current representation
    migrate(config)

    validate(config)

    return config

def migrate(config):
    """Perform conversions to maintain backwards-compatibility"""
    # migrate legacy private_token value if it can be
    # done without overwriting an existing value
    if 'private_token' in config and 'token' not in config:
        config['token'] = config['private_token']
        del config['private_token']

    # default to private tokens if not specified
    if 'token_type' not in config:
        config['token_type'] = 'private'

def refresh_token(config):
    """Use the OAuth refresh token to update an expired access token"""
    access_token, refresh_token = _oauth.refresh(
        config["gitlab_url"],
        config["oauth_client_id"],
        config["refresh_token"])

    # Save updated refresh token on success
    if refresh_token:
        config["token"] = access_token
        config["refresh_token"] = refresh_token
        write(config)

    return access_token

def validate(config):
    """Ensure the configuration meets expectations"""
    required_fields = ('token', 'token_type', 'gitlab_url')
    for field in required_fields:
        if field not in config:
            raise ConfigException(field, 'Required config element is missing. Run "art configure".')

    # warn the user if they have both private_token and token configured
    # the private_token element is a legacy field and should be removed
    if 'private_token' in config and 'token' in config:
        click.secho('Warning: ', nl=False, fg='yellow', err=True)
        click.echo('Config includes both "token" and "private_token" elements. ', nl=False, err=True)
        click.echo('Only the "token" value will be used.', err=True)

def write(config):
    """Save the current configuration to disk"""
    _paths.mkdirs(os.path.dirname(_paths.config_file))
    _yaml.save(_paths.config_file, config)
