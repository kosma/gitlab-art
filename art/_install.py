# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os
import shutil
import stat
import click

from . import _cache
from . import _paths

class InstallUnmatchedError(click.ClickException):
    """An exception raised when an artifact was not found"""

    error = '''Source path(s) did not match any files/non-empty directories in the archive:
  archive: {archive}
  project: {project}
  job: {job}
  ref: {ref}
    {unmatched}'''

    def __init__(self, filename, entry, unmatched):
        unmatched_desc = ('{} => {}'.format(src, dst) for src, dst in unmatched.items())

        message = self.error.format(
            archive=_cache.cache_path(filename),
            unmatched='\n    '.join(unmatched_desc),
            **entry)

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

    def install(self, archive, member):
        """Perform the install action on a zip archive member

        Parameters:
        archive     Archive from which to extract the file
        member      ZipInfo identifying the file to install
        """
        access = None
        filemode_str = ""

        # Translate the archive path to the install destination
        target = self.translate(member.filename)

        # if create_system is Unix (3), external_attr contains filesystem permissions
        if member.create_system == 3:
            filemode = member.external_attr >> 16

            # Keep only the normal permissions bits;
            # ignore special bits like setuid, setgid, sticky
            access = filemode & InstallAction.S_IRWXUGO
            filemode_str = '   ' + stat.filemode(stat.S_IFMT(filemode) | access)

        click.echo('* install: %s => %s%s' % (member.filename, target, filemode_str))

        if member.filename.endswith('/'):
            _paths.mkdirs(target)
        else:
            if os.sep in target:
                _paths.mkdirs(os.path.dirname(target))
            with archive.open(member) as fmember:
                with open(target, 'wb') as ftarget:
                    shutil.copyfileobj(fmember, ftarget)

        if access is not None:
            os.chmod(target, access)

    def __str__(self):
        return '{} => {}'.format(self.src, self.dest)
