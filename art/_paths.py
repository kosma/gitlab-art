import errno
import os

import appdirs


_appdirs = appdirs.AppDirs('art')
artifacts_file = 'artifacts.yml'
artifacts_lock_file = 'artifacts.lock.yml'
config_file = os.path.join(_appdirs.user_config_dir, 'config.yml')
cache_dir = _appdirs.user_cache_dir


def strip_components(path, num):
    """
    Strip "num" leading components from path
    """
    if not path:
        return path

    parts = path.split(os.path.sep)
    if parts[0] == '':
        num += 1

    parts = parts[num:]
    if not parts:
        return ''

    return os.path.join(*parts)

def mkdirs(path):
    """
    Like `os.makedirs`, but doesn't complain if the directory already exist.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
