import errno
import os
import sys

import appdirs


_appdirs = appdirs.AppDirs('art')
artifacts_file = 'artifacts.yml'
artifacts_lock_file = 'artifacts.lock.yml'
config_file = os.path.join(_appdirs.user_config_dir, 'config.yml')
cache_dir = _appdirs.user_cache_dir


def mkdirs(path):
    """
    Like `os.makedirs`, but doesn't complain if the directory already exist.

    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
