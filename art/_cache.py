# -*- coding: utf-8 -*-

from __future__ import absolute_import

import errno
import os
from . import _paths


def save(filename, content):
    path = os.path.join(_paths.cache_dir, filename)
    path_tmp = os.tempnam(_paths.cache_dir)
    with open(path_tmp, 'wb') as stream:
        stream.write(content)
    _paths.mkdirs(os.path.dirname(path))
    os.rename(path_tmp, path)


def get(filename):
    try:
        with open(os.path.join(_paths.cache_dir, filename), 'rb') as stream:
            return stream.read()
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            raise KeyError(filename)
        raise
