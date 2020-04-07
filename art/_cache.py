# -*- coding: utf-8 -*-

from __future__ import absolute_import
from contextlib import contextmanager

import errno
import os
from . import _paths


def cache_path(filename):
    return os.path.join(_paths.cache_dir, filename)

@contextmanager
def save_file(filename):
    path = cache_path(filename)
    path_tmp = path + '.tmp'
    _paths.mkdirs(os.path.dirname(path))
    with open(path_tmp, 'wb') as stream:
        yield stream
    os.rename(path_tmp, path)


def save(filename, content):
    with save_file(filename) as f:
        f.write(content)


def get(filename):
    try:
        return open(cache_path(filename), 'rb')
    except IOError as exc:
        # translate "No such file or directory" into KeyError
        if exc.errno == errno.ENOENT:
            raise KeyError(filename)
        else:
            raise
