# -*- coding: utf-8 -*-

import click

@click.group()
def main():
    """Art, the Gitlab artifact repository client."""


@main.command()
def config():
    """Configure Gitlab URL and access token."""
    click.echo('config')

@main.command()
def fetch():
    """Fetch latest tag/branch commits."""
    click.echo('update')

@main.command()
def download():
    """Download artifacts to local cache."""
    click.echo('download')

@main.command()
def install():
    """Install artifacts to current directory."""
    click.echo('install')
