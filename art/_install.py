# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import shutil
import stat
import click

from . import _cache
from . import _paths

UMASK_VALUE = -1
def _get_umask():
    global UMASK_VALUE
    if UMASK_VALUE != -1:
        return UMASK_VALUE

    UMASK_VALUE = os.umask(0o777)
    os.umask(UMASK_VALUE)
    return UMASK_VALUE

class InstallUnmatchedError(click.ClickException):
    """An exception raised when an artifact was not found"""

    error = '''Source path(s) did not match any files/non-empty directories in the archive:
  archive: {archive}
  project: {project}
  ref: {ref}
  {entry_id_str}
    {unmatched}'''

    def __init__(self, filename, entry, unmatched):
        unmatched_desc = ('{} => {}'.format(src, dst) for src, dst in unmatched.items())
        if 'job_id' in entry:
            entry_id_str = 'job: {} (id={})'.format(entry["job"], entry["job_id"])
        elif 'commit' in entry:
            entry_id_str = 'commit: {}'.format(entry["commit"])
        elif 'package' in entry:
            entry_id_str = 'package: {} (id={})'.format(entry["package"], entry["package_file_id"])

        message = self.error.format(
            archive=_cache.cache_path(filename),
            unmatched='\n    '.join(unmatched_desc),
            **entry,
            entry_id_str=entry_id_str)

        super().__init__(message)

class InstallSourceRequiresExtractionError(click.ClickException):
    """An exception raised when an install source requires extraction, but it is disabled"""

    error = '''Source path "{source_file}" requires artifact extraction, but it is disabled for this item. Use "." to install the unextracted artifact:
  project: {project}
  ref: {ref}
  extract: {extract}
  {entry_id_str}
    {source_file} => {target_file}'''

    def __init__(self, entry, source, target):
        if 'job_id' in entry:
            entry_id_str = 'job: {} (id={})'.format(entry["job"], entry["job_id"])
        elif 'commit' in entry:
            entry_id_str = 'commit: {}'.format(entry["commit"])
        elif 'package' in entry:
            entry_id_str = 'package: {} (id={})'.format(entry["package"], entry["package_file_id"])

        message = self.error.format(
            source_file=source,
            target_file=target,
            **entry,
            entry_id_str=entry_id_str)

        super().__init__(message)


class InstallAction():
    """Represents a user request to install a file from an artifact archive"""

    S_IRWXUGO = 0o0777

    def __init__(self, source, destination, extract):
        self.src = source
        self.dest = destination

        if source == '.':
            # "copy all" filter
            self._match = lambda f: True
            if extract or self.dest.endswith(os.path.sep):
                self.translate = lambda f: os.path.join(self.dest, f)
            else:
                self.translate = lambda f: self.dest
        elif source.endswith('/'):
            # 1:1 directory filter
            self._match = lambda f: f.startswith(self.src)
            self.translate = lambda f: os.path.join(self.dest, f[len(self.src):])
        else:
            # 1:1 file filter
            self._match = lambda f: f == self.src
            self.translate = lambda f: self.dest

    def match(self, filepath):
        """Compare an archive file using the source file pattern
        Arguments:
            filepath    The archive filepath to evaluate

        Returns: True if the pattern matched the filepath, otherwise False
        """
        return self._match(filepath)

    def __str__(self):
        return '{} => {}'.format(self.src, self.dest)


def _source_from_archive(archive, filepath):
    """
    Open the file, identified by filepath, within a ZIP archive
    """
    member = archive.getinfo(filepath)

    # if create_system is Unix (3), external_attr contains filesystem permissions
    if member.create_system == 3:
        filemode = member.external_attr >> 16
    elif member.is_dir():
        filemode = (0o777 ^ _get_umask()) | stat.S_IFDIR
    else:
        filemode = (0o666 ^ _get_umask()) | stat.S_IFREG

    return archive.open(member), filemode


def install(artifact_file, archive, archive_path, target):
    """Perform the install action on the artifact or a zip archive member

    If archive is spec
    Parameters:
    artifact_file An open fileobj for the artifact to install
    archive       An optional zip archive for the artifact_file
    archive_path  The path within archive that identifies the file to install
    target        Destination file path
    """

    fsource = None
    try:
        # If a ZIP archive is provided, obtain the source file using archive_path
        # Otherwise the source file is the artifact itself
        if archive:
            fsource, filemode = _source_from_archive(archive, archive_path)
        else:
            fsource = artifact_file
            filemode = (0o666 ^ _get_umask()) | stat.S_IFREG

        # Keep only the normal permissions bits;
        # ignore special bits like setuid, setgid, sticky
        access = filemode & InstallAction.S_IRWXUGO
        filemode = stat.S_IFMT(filemode) | access

        if target.endswith('/'):
            _paths.mkdirs(target)
        else:
            if os.sep in target:
                _paths.mkdirs(os.path.dirname(target))
            with open(target, 'wb') as ftarget:
                shutil.copyfileobj(fsource, ftarget)
    finally:
        # Only close files we opened
        if fsource != artifact_file:
            fsource.close()

    return target, filemode
