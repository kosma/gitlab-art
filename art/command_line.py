# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import shutil
import stat
import sys
import zipfile
import click
from gitlab import Gitlab
from . import _cache
from . import _config
from . import _paths
from . import _yaml
from . import __version__ as version

S_IRWXUGO = 0o0777

def get_gitlab():
    config = _config.load()
    return Gitlab(config['gitlab_url'], private_token=config['private_token'])


def get_ref_last_successful_job(project, ref, job_name):
    pipelines = project.pipelines.list(as_list=False, ref=ref, order_by='id', sort='desc')
    for pipeline in pipelines:
        jobs = pipeline.jobs.list(as_list=False, scope='success')
        for job in jobs:
            if job.name == job_name:
                # Turn ProjectPipelineJob into ProjectJob
                return project.jobs.get(job.id, lazy=True)

    raise Exception("Could not find latest successful '{}' job for {} ref {}".format(
        job_name, project.path_with_namespace, ref))


def zip_name(project, job_id):
    return os.path.join(project, '{}.zip'.format(job_id))


def install_member(archive, member, target):
    """Install a zip archive member

    Parameters:
    archive     Archive from which to extract the file
    member      ZipInfo identifying the file to extract
    target      Path to which the file is extracted
    """
    access = None
    filemode_str = ""

    # if create_system is Unix (3), external_attr contains filesystem permissions
    if member.create_system == 3:
        filemode = member.external_attr >> 16

        # Keep only the normal permissions bits;
        # ignore special bits like setuid, setgid, sticky
        access = filemode & S_IRWXUGO
        filemode_str = '   ' + stat.filemode(stat.S_IFMT(filemode) | access)

    click.echo('* install: %s => %s%s' % (member.filename, target, filemode_str))
    if os.sep in target:
        _paths.mkdirs(os.path.dirname(target))
    with archive.open(member) as fmember:
        with open(target, 'wb') as ftarget:
            shutil.copyfileobj(fmember, ftarget)

    if access is not None:
        os.chmod(target, access)


@click.group()
@click.version_option(version, prog_name='art')
@click.option('--cache', '-c', help='Download cache directory.')
def main(cache):
    """Art, the Gitlab artifact repository client."""

    # we change the default when running under CI...
    if 'GITLAB_CI' in os.environ:
        _paths.cache_dir = '.art-cache'
    # ...but command-line options always take precedence
    if cache is not None:
        _paths.cache_dir = cache


@main.command()
@click.argument('gitlab_url')
@click.argument('private_token')
def configure(**kwargs):
    """Configure Gitlab URL and access token."""

    _config.save(**kwargs)


@main.command()
def update():
    """Update latest tag/branch job IDs."""

    gitlab = get_gitlab()
    artifacts = _yaml.load(_paths.artifacts_file)

    for entry in artifacts:
        proj = gitlab.projects.get(entry['project'])
        entry['job_id'] = get_ref_last_successful_job(proj, entry['ref'], entry['job']).id
        click.echo('* %s: %s => %s' % (
            entry['project'], entry['ref'], entry['job_id']), sys.stderr)

    _yaml.save(_paths.artifacts_lock_file, artifacts)


@main.command()
def download():
    """Download artifacts to local cache."""

    gitlab = get_gitlab()
    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)

    for entry in artifacts_lock:
        filename = zip_name(entry['project'], entry['job_id'])
        try:
            _cache.get(filename)
        except KeyError:
            click.echo('* %s: %s => downloading...' % (entry['project'], entry['job_id']))
            proj = gitlab.projects.get(entry['project'])
            job = proj.jobs.get(entry['job_id'], lazy=True)
            with _cache.save_file(filename) as f:
                job.artifacts(streamed=True, action=f.write)
            click.echo('* %s: %s => downloaded.' % (entry['project'], entry['job_id']))
        else:
            click.echo('* %s: %s => present' % (entry['project'], entry['job_id']))


@main.command()
def install():
    """Install artifacts to current directory."""

    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)

    for entry in artifacts_lock:
        # convert the "install" dictionary to list of (match, translate)
        installs = []
        for source, destination in entry['install'].items():
            # Nb. Defaults parameters on lambda are required due to derpy
            #     Python closure semantics (scope capture).
            if source == '.':
                # "copy all" filter
                installs.append((
                    lambda f, s=source, d=destination: True,
                    lambda f, s=source, d=destination: os.path.join(d, f)
                ))
            elif source.endswith('/'):
                # 1:1 directory filter
                installs.append((
                    lambda f, s=source, d=destination: f.startswith(s),
                    lambda f, s=source, d=destination: os.path.join(d, f[len(s):])
                ))
            else:
                # 1:1 file filter
                installs.append((
                    lambda f, s=source, d=destination: f == s,
                    lambda f, s=source, d=destination: d
                ))
        # make sure there are no bugs in the lambdas above
        del source, destination # pylint: disable=undefined-loop-variable

        # open the artifacts.zip archive
        filename = zip_name(entry['project'], entry['job_id'])
        archive_file = _cache.get(filename)
        archive = zipfile.ZipFile(archive_file)

        # iterate over the zip archive
        for member in archive.infolist():
            if member.is_dir():
                # skip directories, they will be created as-is
                continue
            for match, translate in installs:
                if match(member.filename):
                    target = translate(member.filename)
                    install_member(archive, member, target)
