# -*- coding: utf-8 -*-

from __future__ import absolute_import

import click

silent = False

def echo(*args, **kwargs):
    global silent

    if not silent:
        click.echo(*args, **kwargs)

def secho(*args, **kwargs):
    global silent

    if not silent:
        click.secho(*args, **kwargs)
