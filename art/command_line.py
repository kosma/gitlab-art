# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import sys
import zipfile
import json

import click
from . import _cache
from . import _config
from . import _gitlab
from . import _install
from . import _paths
from . import _termui
from . import _yaml
from . import __version__ as version

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
                return job.id, pipeline.sha

    raise click.ClickException("Could not find latest successful '{}' job for {} ref {}".format(
        job_name, project.path_with_namespace, ref))

def zip_name(entry):
    """Get the cache-relative path to the archive file for an artifacts.yml entry"""
    source = entry.get('source', 'ci-job')
    if source == 'ci-job':
        zip_key = entry['job_id']
    elif source == 'repository':
        zip_key = 'repo-{}'.format(entry['commit'])

    return os.path.join(entry['project'], '{}.zip'.format(zip_key))

def get_short_id(entry):
    source = entry.get('source', 'ci-job')
    if source == 'repository':
        return entry['commit'][:8]

    return entry['job_id']

def download_archive(gitlab, entry, filename):
    """Download the archive file for an artifacts.yml entry to the cache"""
    source = entry.get('source', 'ci-job')

    entry_short_id = get_short_id(entry)
    if source == 'ci-job':
        entry_id_str = 'job "{}" (id={})'.format(entry['job'], entry_short_id)
    elif source == 'repository':
        entry_id_str = entry['commit']

    _termui.echo('* %s: %s => downloading...' % (entry['project'], entry_short_id))

    fail_msg = 'Failed to download %s from "%s"' % (
        entry_id_str,
        entry['project'])
    with _gitlab.wrap_errors(gitlab, fail_msg):
        # Use shallow objects for proj and job to allow compatibility with
        # job tokens where only the artifacts endpoint is accessible.
        proj = gitlab.projects.get(entry['project'], lazy=True)

        with _cache.save_file(filename) as fileobj:
            if source == 'ci-job':
                job = proj.jobs.get(entry['job_id'], lazy=True)
                job.artifacts(streamed=True, action=fileobj.write)
            elif source == 'repository':
                proj.repository_archive(streamed=True, action=fileobj.write, sha=entry['commit'], format='zip')

    _termui.echo('* %s: %s => downloaded.' % (entry['project'], entry_short_id))


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
@click.option('--token-type', '-t', type=click.Choice(['private', 'job', 'oauth']), default='private')
@click.argument('token_or_client_id')
def configure(**kwargs):
    """Configure Gitlab URL and access token."""

    _config.save(**kwargs)


@main.command()
def update():
    """Update latest tag/branch job IDs."""

    gitlab = _gitlab.get()

    # With current GitLab (16.3, as of this writing)
    # You cannot access the projects and jobs API endpoints using a job token
    if is_using_job_token(gitlab):
        raise _config.ConfigException('token_type', 'A job token cannot be used to update artifacts')

    artifacts = _yaml.load(_paths.artifacts_file)
    if not artifacts:
        raise click.ClickException('The %s file was not found or did not contain any entries' % _paths.artifacts_file)

    for entry in artifacts:
        project = entry.get('project', None)
        ref = entry.get('ref', None)
        source = entry.get('source', 'ci-job')

        if source == 'ci-job':
            job = entry.get('job', None)
            if not job:
                raise click.ClickException('No job was specified for project "%s" ref "%s"' % (project, ref))

            # Get the latest job ID for "ci-job" sources
            fail_msg = 'Failed to get last successful "%s" job for "%s" ref "%s"' % (
                job,
                project,
                ref)
            with _gitlab.wrap_errors(gitlab, fail_msg):
                proj = gitlab.projects.get(project)
                job_id, commit = get_ref_last_successful_job(proj, ref, job)
                entry['job_id'] = job_id
                entry['commit'] = commit
        elif source == 'repository':
            # Resolve the ref to a commit for "repository" sources
            fail_msg = 'Failed to find ref "%s" for "%s"' % (ref, project)
            with _gitlab.wrap_errors(gitlab, fail_msg):
                proj = gitlab.projects.get(project)
                entry['commit'] = proj.commits.get(ref).id

        _termui.echo('* %s: %s => %s' % (project, ref, get_short_id(entry)))

    _yaml.save(_paths.artifacts_lock_file, artifacts)


@main.command()
def download():
    """Download artifacts to local cache."""

    gitlab = _gitlab.get()
    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)

    for entry in artifacts_lock:
        filename = zip_name(entry)

        if _cache.contains(filename):
            _termui.echo('* %s: %s => present' % (entry['project'], get_short_id(entry)))
            continue

        download_archive(gitlab, entry, filename)

@main.command()
@click.option('--keep-empty-dirs', '-k', default=False, is_flag=True, help='Do not prune empty directories.')
@click.option('--json', '-j', 'output_json', default=False, is_flag=True, help='Output artifact information to JSON')
def install(keep_empty_dirs, output_json):
    """Install artifacts to current directory."""

    gitlab = _gitlab.get()
    if output_json:
        _termui.silent = True

    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)
    
    # Explanation of relevant keys for each entry:
    #
    # entry["install"]: Requests to install files that match the indicated
    #                   source pattern, from the artifact to the target location.
    # entry["files"]: Files within the artifact that match the install requests
    #                 and will be installed by "art install".
    for entry in artifacts_lock:
        source = entry.get('source', 'ci-job')

        # files installed for this entry
        entry['files'] = []

        # dictionary of src:dest pairs representing artifacts to install
        # make a copy as to not modify the original `artifact_lock` object
        install_requests = entry['install'].copy()

        # create an InstallAction (file match and translate) for each request
        actions = [_install.InstallAction(src, dest) for src, dest in install_requests.items()]

        # open the artifacts.zip archive
        archive_file = get_cached_archive(gitlab, entry)
        archive = zipfile.ZipFile(archive_file)

        # iterate over the zip archive
        for member in archive.infolist():
            filepath = member.filename

            # Skip directory members
            # - Parent directories are created when installing files
            # - The keep_empty_dirs option preserves the original archive tree
            if not keep_empty_dirs and filepath.endswith('/'):
                continue

            # strip leading directory from repository archives
            if source == 'repository':
                filepath = _paths.strip_components(filepath, 1)

            # perform installs that match this member
            for action in actions:
                if not action.match(filepath):
                    continue

                installed_target, filemode_str = action.install(archive, filepath, member)

                # remove requests that are successfully installed
                install_requests.pop(action.src, None)

                # add entry for this file/directory to the entry (to be used in the JSON output)
                entry['files'].append(installed_target)

        # Close zip and archive file
        # No try/finally/with here to reduce nesting, we'd exit anyway
        archive.close()
        archive_file.close()

        # Report an error if any requested artifacts were not installed
        if install_requests:
            raise _install.InstallUnmatchedError(zip_name(entry), entry, install_requests)

    if output_json:
        json.dump(artifacts_lock, sys.stdout, indent=2)
        sys.stdout.write(os.linesep)
