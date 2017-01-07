# -*- coding: utf-8 -*-

from __future__ import absolute_import

import click
from . import artifacts
from . import config
from . import gitlab


@click.group()
def main():
    """Art, the Gitlab artifact repository client."""


@main.command()
@click.argument('gitlab_url')
@click.argument('private_token')
def configure(**kwargs):
    """Configure Gitlab URL and access token."""

    config.save(**kwargs)


@main.command()
def update():
    """Update latest tag/branch commits."""

    c = config.guess_from_env() or config.load()
    g = gitlab.Gitlab(**c)

    a = artifacts.load()
    for e in a:
        e['commit'] = g.get_ref_commit(e['project'], e['ref'])
    artifacts.save(a)


@main.command()
def download():
    """Download artifacts to local cache."""
    click.echo('download')


@main.command()
def install():
    """Install artifacts to current directory."""
    click.echo('install')
