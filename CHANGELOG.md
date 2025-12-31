# Change Log
A summary of significant changes within each version of `gitlab-art`.

## v0.5.0
- ENH: `art configure` supports `--token-type oauth` for interactive authentication using a browser.
- ENH: New `source: 'repository'` attribute in `artifacts.yml` supports installing git repository files.
- ENH: New `source: 'generic-package'` attribute in `artifacts.yml` supports installing files from GitLab's generic package registry.
- ENH: New `extract: yes/no` attribute in `artifacts.yml` can disable ZIP archive extraction to install non-archive artifacts.
- ENH: New `files` attribute in `artifacts.lock.yml` lists every installed file and the source path that matched an install request.
- ENH: Add --json option to `update` and `install` commands which outputs the command result in JSON format.
- ENH: New `art cache` command displays the disk space used by cached artifacts and facillitates their removal.
- ENH: New `art clean` command and `art update --clean` can be used to remove installed files.
- ENH: The `art` command includes a top-level `-C, --change-dir DIR` option to set the working directory before loading `artifacts.yml` and installing files.
- ENH: The `art` command incluces a top-level `-f, --file FILE` option to specify a different name or path to the `artifacts.yml` file.
- BUG: The `appdirs` project has been replaced with `platformdirs`

## v0.4.0
- ENH: Added support for downloading and installing artifacts during CI using GitLab job tokens via `-t, --token-type` option of "art configure".
- ENH: New `-k, --keep-empty-dirs` option of "art install" will preserve empty directories when installing a directory tree from an archive.
- ENH: The install command will download artifacts when necessary, eliminating the need for an explicit "art download".
- ENH: Improve the quality of error messages caused by some common configuration or environmental issues.
- BUG: Report failures when an install request did not match a file in the downloaded archive.
