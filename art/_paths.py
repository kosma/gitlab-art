import errno
import os
import sys

import appdirs


_appdirs = appdirs.AppDirs('art')
artifacts_file = 'artifacts.yml'
artifacts_lock_file = 'artifacts.lock.yml'
config_file = os.path.join(_appdirs.user_data_dir, 'config.yml')
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


def check_artifacts_lock_file():
    """
    Ensure that the 'lock' file exists and is fresh.

    """
    argv0 = os.path.basename(sys.argv[0])
    if not os.path.exists(artifacts_lock_file):
        print >>sys.stderr, "Error: lock file does not exist. Please run '%s update'." % argv0
        sys.exit(1)
    if os.path.getmtime(artifacts_file) > os.path.getmtime(artifacts_lock_file):
        print >>sys.stderr, "Error: lock file is out of date. Please run '%s update'." % argv0
        sys.exit(1)
