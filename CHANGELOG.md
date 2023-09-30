# Change Log
A summary of significant changes within each version of `gitlab-art`.

## v0.4.0
- ENH: Added support for downloading and installing artifacts during CI using GitLab job tokens via `-t, --token-type` option of "art configure".
- ENH: New `-k, --keep-empty-dirs` option of "art install" will preserve empty directories when installing a directory tree from an archive.
- ENH: The install command will download artifacts when necessary, eliminating the need for an explicit "art download".
- ENH: Improve the quality of error messages caused by some common configuration or environmental issues.
- BUG: Report failures when an install request did not match a file in the downloaded archive.
