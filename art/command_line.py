# -*- coding: utf-8 -*-

from __future__ import absolute_import

import contextlib
import fnmatch
import math
import os
import stat
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
    pipelines = project.pipelines.list(ref=ref, order_by='id', sort='desc', iterator=True)
    for pipeline in pipelines:
        jobs = pipeline.jobs.list(scope='success', iterator=True)
        try:
            job = next(job for job in jobs if job.name == job_name)
            artifact = next(artifact for artifact in job.artifacts if artifact['file_type'] == 'archive')
            return job.id, artifact['filename'], pipeline.sha
        except StopIteration:
            continue

    raise click.ClickException("Could not find latest successful '{}' job for {} ref {}".format(
            job_name, project.path_with_namespace, ref))

def artifact_name(entry):
    """Get the cache-relative path to the archive file for an artifacts.yml entry"""
    source = entry.get('source', 'ci-job')

    fileext = '.zip'
    if source == 'ci-job':
        filename = entry['job_id']
    elif source == 'repository':
        filename = 'repo-{}'.format(entry['commit'])
    elif source == 'generic-package':
        filename = 'pkg-{}'.format(entry['package_file_id'])
        fileext = ''

    return os.path.join(entry['project'], '{}{}'.format(filename, fileext))

def zip_archive(entry, fileobj):
    try:
        return zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile as exc:
        archive_path = _cache.cache_path(artifact_name(entry))
        raise click.ClickException('Cannot extract artifact "%s" for project "%s": %s' % (archive_path, entry['project'], str(exc)))

def canonical_request_path(entry, path):
    """Get the install request path from an archive path"""
    source = entry.get('source', 'ci-job')

    # strip leading directory from repository archive paths
    # a repository archive includes a top-level directory based on the project name and git ref
    # this is undesirable for artifacts.yml because install request paths would have to be updated
    # whenever the project's ref is updated.
    if source == 'repository':
        return _paths.strip_components(path, 1)

    return path

def get_files_for_entry(gitlab, entry, keep_empty_dirs):
    """Build the list of archive files that match the install requests for an entry"""
    files = []

    # Explanation of relevant keys for each entry:
    #
    # entry["install"]: Requests to install files that match the indicated
    #                   source pattern, from the artifact to the target location.
    # entry["files"]: Files within the artifact that match the install requests
    #                 and will be installed by "art install".
    # List of src:dest pairs representing artifacts to install
    # make a copy as to not modify the original `artifact_lock` object
    install_requests = entry['install'].copy()

    # Determine if the sources need to be extracted from the artifact (default=yes)
    extract = entry.get('extract', True)

    # create an InstallAction (file match and translate) for each request
    actions = [_install.InstallAction(src, dest, extract) for src, dest in install_requests.items()]

    # If extraction is disabled, the source for all actions is the artifact itself
    if not extract:
        for action in actions:
            # Only the "copy all" source is valid for artifacts that aren't extracted
            if action.src != '.':
                raise _install.InstallSourceRequiresExtractionError(entry, action.src, action.dest)

            artifact_filename = entry['filename']
            files.append({ artifact_filename: action.translate(artifact_filename) })

        return files

    # open the artifact file for extraction
    with open_install_source(gitlab, entry) as (artifact_file, archive):
        # iterate over the zip archive
        for member in archive.infolist():
            filepath = member.filename

            # Skip directory members
            # - Parent directories are created when installing files
            # - The keep_empty_dirs option allows an install request to match and create an empty directory
            if not keep_empty_dirs and filepath.endswith('/'):
                continue

            # Canonicalize the archive path before matching the install request
            filepath = canonical_request_path(entry, filepath)

            # Check if this file matches an install request
            for action in actions:
                if not action.match(filepath):
                    continue

                files.append({ member.filename: action.translate(filepath) })

                # Remove the install request from the list now that it's been fulfilled
                install_requests.pop(action.src, None)

    # Report an error if any requested files were not found in the source archive
    if install_requests:
        raise _install.InstallUnmatchedError(artifact_name(entry), entry, install_requests)

    return files

def get_short_id(entry):
    source = entry.get('source', 'ci-job')
    if source == 'repository':
        return entry['commit'][:8]
    elif source == 'generic-package':
        return entry['package_file_id']

    return entry['job_id']

def download_artifact(gitlab, entry, filename):
    """Download the artifact file for an artifacts.yml entry to the cache"""
    source = entry.get('source', 'ci-job')

    entry_short_id = get_short_id(entry)
    if source == 'ci-job':
        entry_id_str = 'job "{}" (id={})'.format(entry['job'], entry_short_id)
    elif source == 'repository':
        entry_id_str = 'commit "{}"'.format(entry['commit'])
    elif source == 'generic-package':
        entry_id_str = 'package file "{}" (tag {})'.format(entry['filename'], entry['ref'])

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
            elif source == 'generic-package':
                # Download the generic package file
                proj.generic_packages.download(streamed=True, action=fileobj.write,
                    package_name=entry['package'],
                    package_version=entry['ref'],
                    file_name=entry['filename']
                )

    _termui.echo('* %s: %s => downloaded.' % (entry['project'], entry_short_id))


def open_cached_artifact(gitlab, entry):
    """Open the archive file for an entry. Download if necessary"""

    filename = artifact_name(entry)
    try:
        return _cache.get(filename)
    except KeyError:
        pass

    download_artifact(gitlab, entry, filename)

    try:
        return _cache.get(filename)
    except KeyError as exc:
        msg = 'File "%s" was not found after download' % _cache.cache_path(filename)
        raise click.ClickException(msg) from exc

@contextlib.contextmanager
def open_install_source(gitlab, entry):
    archive = None
    archive_file = None
    extract = entry.get('extract', True)
    try:
        archive_file =  open_cached_artifact(gitlab, entry)
        if extract:
            archive = zip_archive(entry, archive_file)

        yield archive_file, archive
    finally:
        if archive:
            archive.close()
        if archive_file:
            archive_file.close()

@click.group()
@click.version_option(version, prog_name='art')
@click.option('--cache', '-c', help='Download cache directory.')
@click.option('--change-dir', '-C', metavar='DIR', type=click.Path(exists=True, file_okay=False, resolve_path=True),  help='Run as if art was started from DIR')
@click.option('--file', '-f', metavar='FILE', type=click.Path(dir_okay=False), help='Use FILE as artifacts.yml')
def main(cache=None, change_dir=None, file=None):
    """Art, the Gitlab artifact repository client."""

    if change_dir:
        os.chdir(change_dir)

    if file:
        if not os.path.exists(file):
            raise click.ClickException('The file "%s" was not found' % os.path.abspath(file))
        _paths.artifacts_file = file
        _paths.artifacts_lock_file = _paths.lockfile(file)

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
@click.option('--keep-empty-dirs', '-k', default=False, is_flag=True, help='Do not prune empty directories.')
@click.option('--json', '-j', 'output_json', default=False, is_flag=True, help='Output artifact information to JSON')
@click.option('-c', '--clean', default=False, is_flag=True, help='Remove installed files before updating lock file')
def update(keep_empty_dirs, output_json, clean):
    """Update latest tag/branch job IDs."""

    if output_json:
        _termui.silent = True

    if clean:
        artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
        remove_installed_files(artifacts_lock, False)

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
                job_id, filename, commit = get_ref_last_successful_job(proj, ref, job)
                entry['job_id'] = job_id
                entry['commit'] = commit
                entry['filename'] = filename
        elif source == 'repository':
            # Resolve the ref to a commit for "repository" sources
            fail_msg = 'Failed to find ref "%s" for "%s"' % (ref, project)
            with _gitlab.wrap_errors(gitlab, fail_msg):
                proj = gitlab.projects.get(project)
                entry['commit'] = proj.commits.get(ref).id
                entry['filename'] = "{}-{}.zip".format(proj.path, ref)
        elif source == 'generic-package':
            # Resolve the package_file_id for "generic-package" sources
            package = entry.get('package', None)
            if not package:
                raise click.ClickException('No package was specified for project "%s" ref "%s"' % (project, ref))

            filename = entry.get('filename', None)
            if not filename:
                raise click.ClickException('No filename was specified for package "%s" of project "%s" ref "%s"' % (package, project, ref))

            fail_msg = 'Failed to get package "%s %s" for "%s"' % (package, ref, project)
            with _gitlab.wrap_errors(gitlab, fail_msg):
                proj = gitlab.projects.get(project)
                packages = proj.packages.list(package_type='generic', package_name=package, package_version=ref, get_all=True)

            if len(packages) != 1:
                raise click.ClickException('More than 1 package with name %s for %s %s' % (package, ref, project))

            package = packages[0]

            fail_msg = 'Failed to get file "%s/%s %s" for "%s"' % (package, filename, ref, project)
            with _gitlab.wrap_errors(gitlab, fail_msg):
                files = package.package_files.list(get_all=True)
                file = next(f for f in files if f.file_name == filename)

            entry['package_id']= package.id
            entry['package_file_id']= file.id
        else:
            raise click.ClickException('Unknown artifact source: "%s"' % (source,))

        # Process the artifact and find files that match the install requests
        entry['files'] = get_files_for_entry(gitlab, entry, keep_empty_dirs)

        _termui.echo('* %s: %s => %s' % (project, ref, get_short_id(entry)))

    _yaml.save(_paths.artifacts_lock_file, artifacts)

    if output_json:
        json.dump(artifacts, sys.stdout, indent=2)
        sys.stdout.write(os.linesep)


@main.command()
def download():
    """Download artifacts to local cache."""

    gitlab = _gitlab.get()
    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)

    for entry in artifacts_lock:
        filename = artifact_name(entry)

        if _cache.contains(filename):
            _termui.echo('* %s: %s => present' % (entry['project'], get_short_id(entry)))
            continue

        download_artifact(gitlab, entry, filename)

@main.command()
@click.option('--keep-empty-dirs', '-k', default=False, is_flag=True, hidden=True, help='Do not prune empty directories.')
@click.option('--json', '-j', 'output_json', default=False, is_flag=True, help='Output artifact information to JSON')
def install(keep_empty_dirs, output_json):
    """Install artifacts to current directory."""

    if output_json:
        _termui.silent = True

    gitlab = _gitlab.get()

    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)

    for entry in artifacts_lock:
        # The list of matching files is recorded by art update, but older artifacts.lock.yml
        # files may be missing this attribute. Create it now, if necessary.
        #
        # --keep-empty-dirs is a deprecated install option, as it has moved to "art update". If
        # a user specified it here, they may be expecting an older art version and may not have included
        # the option during "art update". Rebuild the files list to ensure the option isn't ignored.
        files = entry.get('files', None)
        if not files or keep_empty_dirs:
            files = get_files_for_entry(gitlab, entry, keep_empty_dirs)

        with open_install_source(gitlab, entry) as (artifact_file, archive):
            permissions = {}
            for file_spec in files:
                filepath, target = next(iter(file_spec.items()))
                target, filemode = _install.install(artifact_file, archive, filepath, target)

                # File permissions are applied in a second pass. This prevents restrictive
                # permissions from preventing extraction (e.g. a non-empty, read-only directory)
                # without requiring depth-first traversal
                permissions[target] = filemode

                filemode_str = '   ' + stat.filemode(filemode)
                request_path = canonical_request_path(entry, filepath)
                _termui.echo('* install: %s => %s%s' % (request_path, target, filemode_str))

            for target, filemode in permissions.items():
                os.chmod(target, filemode)

    if output_json:
        json.dump(artifacts_lock, sys.stdout, indent=2)
        sys.stdout.write(os.linesep)

def remove_installed_files(artifacts_lock, dry_run):
    """Remove files installed via art install"""
    if not artifacts_lock:
        return

    action = "would be removed" if dry_run else "removed"
    for entry in artifacts_lock:
        project = entry.get('project')
        files = entry.get('files', None)

        # Build file list if the lock file was created from older art
        if not files:
            gitlab = _gitlab.get()
            files = get_files_for_entry(gitlab, entry, False)

        for file_spec in files:
            target = next(iter(file_spec.values()))
            if not os.path.exists(target):
                continue

            if not dry_run:
                _paths.remove(target)
            _termui.echo('* %s: %s' % (action, target,))

@main.command()
@click.option('-d', '--dry-run', default=False, is_flag=True, help='Report artificats that would be removed without removing them')
def clean(dry_run):
    """Remove installed files"""
    artifacts_lock = _yaml.load(_paths.artifacts_lock_file)
    if not artifacts_lock:
        raise click.ClickException('No entries in %s file. Run "art update" first.' % _paths.artifacts_lock_file)

    remove_installed_files(artifacts_lock, dry_run)

@main.group()
def cache():
    """Inspect and manage the artifact cache"""
    pass

@cache.command()
@click.option('--sort-size', '-s', default=False, is_flag=True, help='Sort results by size')
@click.option('--human-readable', '-h', default=False, is_flag=True, help='Print sizes with units rather than bytes')
def list(sort_size, human_readable):
    """List projects with cached artifacts and their size"""
    archives = _cache.list()

    sort_key = lambda item: item[0]
    if sort_size:
        sort_key = lambda item: item[1]['size']
    sorted_archives = sorted(archives.items() , key=sort_key, reverse=sort_size)

    # convert sizes as string
    for project in archives:
        size = archives[project]['size']
        if human_readable:
            units = ['B', 'K', 'M', 'G', 'T', 'P']
            unit = int(math.log2(size) // math.log2(1024))
            archives[project]['size'] = '{:0.1f}{}'.format(size / (1024 ** unit), units[unit])
        else:
            archives[project]['size'] = str(size)

    # calculate column sizes for justification
    column_sizes = [len('PROJECT'), len('SIZE')]
    for project in archives:
        name_len = len(project)
        if name_len > column_sizes[0]:
            column_sizes[0] = name_len + 1
        size_len = len(archives[project]['size'])
        if size_len > column_sizes[1]:
            column_sizes[1] = size_len + 1

    _termui.echo("PROJECT".ljust(column_sizes[0]), nl=False)
    _termui.echo("SIZE".rjust(column_sizes[1]))
    for project in dict(sorted_archives):
        _termui.echo(project.ljust(column_sizes[0]), nl=False)
        _termui.echo(archives[project]['size'].rjust(column_sizes[1]))

@cache.command()
@click.argument('patterns', metavar='PATTERN', nargs=-1)
@click.option('-d', '--dry-run', default=False, is_flag=True, help='Report artificats that would be removed without removing them')
def purge(patterns, dry_run):
    """Remove cached artifacts. PATTERN can be a project path or shell-style glob expression."""
    archives = _cache.list()

    if not patterns:
        to_remove = archives.keys()
    else:
        to_remove = []
        unmatched_patterns = []
        for glob in patterns:
            matched = fnmatch.filter(archives.keys(), glob)
            if matched:
                to_remove = to_remove + matched
            else:
                unmatched_patterns.append(glob)

        if unmatched_patterns:
            msg = '\n    '.join(unmatched_patterns)
            raise click.ClickException("No cached files were found for projects matching:\n    {}".format(msg))

    action = "would be removed" if dry_run else "removed"
    for project in set(to_remove):
        for filepath in archives[project]['files']:
            if not dry_run:
                _paths.remove(filepath)
            _termui.echo('* %s: %s => %s.' % (project, os.path.basename(filepath), action))
