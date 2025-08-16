# -*- coding: utf-8 -*-
from __future__ import absolute_import

import contextlib

import click
import requests
from gitlab import exceptions as GitlabExceptions
from gitlab import Gitlab

from . import _config

def get():
    """
    Create a GitLab API object from the current configuration
    """

    config = _config.load()
    gitlab_url = config['gitlab_url']
    token = config['token']
    if config['token_type'] == 'private':
        return Gitlab(gitlab_url, private_token=token)
    if config['token_type'] == 'job':
        return Gitlab(gitlab_url, job_token=token)
    if config['token_type'] == 'oauth':
        gitlab = Gitlab(gitlab_url, oauth_token=token)

        # OAuth tokens are only valid for 2 hours. Verify that the stored
        # token isn't expired
        if token and test_token(gitlab):
            return gitlab

        # If expired, use the refresh token to get a new one
        token = _config.refresh_token(config)
        return Gitlab(gitlab_url, oauth_token=token)

    raise _config.ConfigException('token_type', 'Unknown token type: {}'.format(config['token_type']))

# Try to use the authentication token
def test_token(gitlab):
    """
    Use GitLab's auth API endpoint to check for a valid access token

    Returns True if the token can be used access the API.
    """
    with wrap_errors(gitlab, "Authentication failed"):
        try:
            gitlab.auth()
            return True
        except GitlabExceptions.GitlabAuthenticationError:
            pass

    return False

@contextlib.contextmanager
def wrap_errors(gitlab, fail_msg=None):
    """Centralize common GitLab exception handling"""
    try:
        yield
    except requests.exceptions.SSLError as exc:
        raise click.ClickException('TLS connection to %s failed: %s' % (gitlab.url, exc))
    except requests.exceptions.ConnectionError as exc:
        raise click.ClickException('Connection to %s failed: %s' % (gitlab.url, exc))
    except GitlabExceptions.GitlabAuthenticationError as exc:
        raise click.ClickException('GitLab authentication failed: %s' % exc)
    except GitlabExceptions.GitlabOperationError as exc:
        msg = str(exc)
        if fail_msg:
            msg = '%s: %s' % (fail_msg, exc)

        raise click.ClickException(msg)
