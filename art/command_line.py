# -*- coding: utf-8 -*-

from __future__ import absolute_import

import contextlib
import os
import sys
import zipfile

import click
import requests
from gitlab import exceptions as GitlabExceptions
from gitlab import Gitlab
from . import _cache
from . import _config
from . import _install
from . import _paths
from . import _yaml
from . import __version__ as version

def get_gitlab():
    config = _config.load()
    if config['token_type'] == 'private':
        return Gitlab(config['gitlab_url'], private_token=config['token'])
    if config['token_type'] == 'job':
        return Gitlab(config['gitlab_url'], job_token=config['token'])

    raise _config.ConfigException('token_type', 'Unknown token type: {}'.format(config['token_type']))


@contextlib.contextmanager
def try_gitlab(gitlab, fail_msg=None):
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

def is_using_job_token(gitlab):
    """Determine if the GitLab client will use a job token to authenticate.

    Job tokens cannot access the full GitLab API. See the documentation here:
    https://docs.gitlab.com/ee/ci/jobs/ci_job_token.html

    The client only uses a job token when other tokens are unavailable.
    """
    # private and oauth tokens will be used, if available
    if gitlab.private_token is not None or gitlab.oauth_token is not None:
        return False

    return gitlab.job_token is not None


def get_ref_last_successful_job(project, ref, job_name):
    pipelines = project.pipelines.list(as_list=False, ref=ref, order_by='id', sort='desc')
    for pipeline in pipelines:
        jobs = pipeline.jobs.list(as_list=False, scope='success')
        for job in jobs:
            if job.name == job_name:
                # Turn ProjectPipelineJob into ProjectJob
                return project.jobs.get(job.id, lazy=True)

    raise click.ClickException("Could not find latest successful '{}' job for {} ref {}".format(
        job_name, project.path_with_namespace, ref))


def zip_name(entry):
    """Get the cache-relative path to the archive file for an artifacts.yml entry"""

    return os.path.join(entry['project'], '{}.zip'.format(entry['job_id']))


def download_archive(gitlab, entry, filename):
    """Download the archive file for an artifacts.yml entry"""

    click.echo('* %s: %s => downloading...' % (entry['project'], entry['job_id']))

    fail_msg = 'Failed to download job "%s" (id=%s) from "%s"' % (
        entry['job'],
        entry['job_id'],
        entry['project'])

    with try_gitlab(gitlab, fail_msg):
        # Use shallow objects for proj and job to allow compatibility with
        # job tokens where only the artifacts endpoint is accessible.
        proj = gitlab.projects.get(entry['project'], lazy=True)
        job = proj.jobs.get(entry['job_id'], lazy=True)

        with _cache.save_file(filename) as fileobj:
            job.artifacts(streamed=True, action=fileobj.write)

    click.echo('* %s: %s => downloaded.' % (entry['project'], entry['job_id']))


def get_cached_archive(gitlab, entry):
    """Open the archive file for an entry. Download if necessary"""

    filename = zip_name(entry)
    try:
        return _cache.get(filename)
    except KeyError:
        pass

    download_archive(gitlab, entry, filename)
    try:
        return _cache.get(filename)
    except KeyError as exc:
        msg = 'File "%s" was not found after download' % _cache.cache_path(filename)
        raise click.ClickException(msg) from exc

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
@click.option('--token-type', '-t', type=click.Choice(['private', 'job']), default='private')
@click.argument('token')
def configure(**kwargs):
    """Configure Gitlab URL and access token."""

    _config.save(**kwargs)


@main.command()
def update():
    """Update latest tag/branch job IDs."""

    gitlab = get_gitlab()

    # With current GitLab (16.3, as of this writing)
    # You cannot access the projects and jobs API endpoints using a job token
    if is_using_job_token(gitlab):
        raise _config.ConfigException('token_type', 'A job token cannot be used to update artifacts')

    artifacts = _yaml.load(_paths.artifacts_file)
    if not artifacts:
        raise click.ClickException('The %s file was not found or did not contain any entries' % _paths.artifacts_file)

    for entry in artifacts:
        fail_msg = 'Failed to get last successful "%s" job for "%s" ref "%s"' % (
            entry['job'],
            entry['project'],
            entry['ref'])
        with try_gitlab(gitlab, fail_msg):
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
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)

    for entry in artifacts_lock:
        filename = zip_name(entry)
        if _cache.contains(filename):
            click.echo('* %s: %s => present' % (entry['project'], entry['job_id']))
            continue

        download_archive(gitlab, entry, filename)

@main.command()
@click.option('--keep-empty-dirs', '-k', default=False, is_flag=True, help='Do not prune empty directories.')
def install(keep_empty_dirs):
    """Install artifacts to current directory."""

    gitlab = get_gitlab()
    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)

    for entry in artifacts_lock:
        # dictionary of src:dest pairs representing artifacts to install
        install_requests = entry['install']

        # create an InstallAction (file match and translate) for each request
        actions = [_install.InstallAction(src, dest) for src, dest in install_requests.items()]

        # open the artifacts.zip archive
        archive_file = get_cached_archive(gitlab, entry)
        archive = zipfile.ZipFile(archive_file)

        # iterate over the zip archive
        for member in archive.infolist():
            # Skip directory members
            # - Parent directories are created when installing files
            # - The keep_empty_dirs option preserves the original archive tree
            if not keep_empty_dirs and member.filename.endswith('/'):
                continue

            # perform installs that match this member
            for action in actions:
                if not action.match(member.filename):
                    continue

                action.install(archive, member)

                # remove requests that are successfully installed
                install_requests.pop(action.src, None)

        # Close zip and archive file
        # No try/finally/with here to reduce nesting, we'd exit anyway
        archive.close()
        archive_file.close()

        # Report an error if any requested artifacts were not installed
        if install_requests:
            raise _install.InstallUnmatchedError(zip_name(entry), entry, install_requests)
