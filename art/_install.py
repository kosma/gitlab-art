# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import shutil
import stat
import click

from . import _cache
from . import _paths
from . import _termui

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
        if 'commit' in entry:
            entry_id_str = 'commit: {}'.format(entry["commit"])
        elif 'job_id' in entry:
            entry_id_str = 'job: {} (id={})'.format(entry["job"], entry["job_id"])

        message = self.error.format(
            archive=_cache.cache_path(filename),
            unmatched='\n    '.join(unmatched_desc),
            **entry,
            entry_id_str=entry_id_str)

        super().__init__(message)

class InstallAction():
    """Represents a user request to install a file from an artifact archive"""

    S_IRWXUGO = 0o0777

    def __init__(self, source, destination):
        self.src = source
        self.dest = destination

        if source == '.':
            # "copy all" filter
            self._match = lambda f: True
            self.translate = lambda f: os.path.join(self.dest, f)
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

    def install(self, archive, filepath, member):
        """Perform the install action on a zip archive member

        Parameters:
        archive     Archive from which to extract the file
        member      ZipInfo identifying the file to install
        """
        access = None
        filemode_str = ""

        # Translate the archive path to the install destination
        target = self.translate(filepath)

        # if create_system is Unix (3), external_attr contains filesystem permissions
        if member.create_system == 3:
            filemode = member.external_attr >> 16
        elif member.is_dir():
            filemode = (0o777 ^ _get_umask()) | stat.S_IFDIR
        else:
            filemode = (0o666 ^ _get_umask()) | stat.S_IFREG

        # Keep only the normal permissions bits;
        # ignore special bits like setuid, setgid, sticky
        access = filemode & InstallAction.S_IRWXUGO
        filemode_str = '   ' + stat.filemode(stat.S_IFMT(filemode) | access)

        _termui.echo('* install: %s => %s%s' % (filepath, target, filemode_str))

        if target.endswith('/'):
            _paths.mkdirs(target)
        else:
            if os.sep in target:
                _paths.mkdirs(os.path.dirname(target))
            with archive.open(member) as fmember:
                with open(target, 'wb') as ftarget:
                    shutil.copyfileobj(fmember, ftarget)

        os.chmod(target, access)

        return target, filemode_str

    def __str__(self):
        return '{} => {}'.format(self.src, self.dest)
