# -*- coding: utf-8 -*-

from __future__ import absolute_import

import sys
import click
from . import _cache
from . import _config
from . import _gitlab
from . import _paths
from . import _yaml


@click.group()
def main():
    """Art, the Gitlab artifact repository client."""


@main.command()
@click.argument('gitlab_url')
@click.argument('private_token')
def configure(**kwargs):
    """Configure Gitlab URL and access token."""

    _config.save(**kwargs)


@main.command()
def update():
    """Update latest tag/branch commits."""

    config = _config.guess_from_env() or _config.load()
    gitlab = _gitlab.Gitlab(**config)
    artifacts = _yaml.load(_paths.artifacts_file)

    for entry in artifacts:
        entry['commit'] = gitlab.get_ref_commit(entry['project'], entry['ref'])
        entry['build_id'] = gitlab.get_commit_last_successful_build(entry['project'], entry['commit'], entry['build'])
        click.echo('* %s: %s => %s => %s' % (
            entry['project'], entry['ref'], entry['commit'], entry['build_id']), sys.stderr)

    _yaml.save(_paths.artifacts_lock_file, artifacts)


@main.command()
def download():
    """Download artifacts to local cache."""

    config = _config.guess_from_env() or _config.load()
    gitlab = _gitlab.Gitlab(**config)
    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)

    for entry in artifacts_lock:
        filename = '%s/%s.zip' % (entry['project'], entry['build_id'])
        try:
            archive = _cache.get(filename)
        except KeyError:
            click.echo('* %s: %s => downloading...' % (entry['project'], entry['build_id']))
            archive = gitlab.get_artifacts_zip(entry['project'], entry['build_id'])
            _cache.save(filename, archive)
            click.echo('* %s: %s => downloaded.' % (entry['project'], entry['build_id']))
        else:
            click.echo('* %s: %s => present' % (entry['project'], entry['build_id']))


@main.command()
def install():
    """Install artifacts to current directory."""
    click.echo('install')
