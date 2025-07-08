# art - cross-project Gitlab artifact dependencies

`art` solves a burning problem of pulling artifacts from different repositories.

## Quickstart

1. Create a Gitlab private token and save it in `art` configuration:

    ```shell
    art configure https://gitlab.example.com/ --token-type private 'as1!df2@gh3#jk4$'
    ```

2. Create `artifacts.yml` with definitions of needed artifacts:

    ```yaml
    - project: kosma/foobar-documentation
      ref: branches/stable
      job: doc
      install:
        build/apidoc/html/: docs/api/
        VERSION: docs/VERSION
    - project: kosma/foobar-firmware
      ref: 1.4.0
      job: firmware-8051
      install:
        build/8051/release/firmware.bin: blobs/firmware-8051.blob
    - project: kosma/foobar-icons
      ref: 69881ebc852f5e02b8328c6b9da615e90b7184b2
      job: icons
      install:
        .: icons/
    ```

3. Run `art update` to automatically determine latest versions and job numbers
   of needed projects and save them into `artifacts.lock.yml`. Commit both files
   to version control system.

4. Run `art download` to fetch required artifacts to your local cache and
   `art install` to install them to the project directory.

## The Lockfile

The `artifacts.lock.yml` is conceptually similar to Ruby's `Gemfile.lock`: it
allows locking to exact revisions and jobs while still semantically tracking
tags or branches and allowing easy updates when needs arise. The following good
practices should be followed:

* Always run `art update` after editing `artifacts.yml`.
* Always commit both files to version control.
* Do not run `art update` automatically unless you enjoy breaking the build.

## Continuous integration

Add the following commands to your `.gitlab-ci.yml`:

```yaml
before_script:
  - sudo pip install https://github.com/kosma/art
  - art configure <url> --token-type {private,job} <token>
  - art download
  - art install
cache:
  paths:
    - .art-cache/
```

## Installed files

The locations of the installed files along with their originating project, version
(ref) and job_id can be outputted to stdout as JSON with the install option
`--json`.

The output is a **JSON array**, where each element is an object with the following
fields:

| Field     | Type     | Required | Default     | Description                                                                      |
|-----------|----------|----------|-------------|----------------------------------------------------------------------------------|
| `install` | object   | yes      | []          | A dictionary of the artifact's files/directories and destination path to install |
| `job`     | string   | yes      | -           | Artifact's job name                                                              |
| `job_id`  | integer  | yes      | -           | Artifact's job id                                                                |
| `project` | string   | yes      | -           | Artifact's project name                                                          |
| `ref`     | integer  | yes      | -           | Artifact's ref                                                                   |
| `files`   | object   | yes      | []          | Full paths of all files installed from the Artifact                              |

A simple example output is below

```bash
art install --json
[
  {
    "install": {
      "artifact_dir/": "local_dir/",
      "foobar.txt": "foobar.txt"
    },
    "job": "art",
    "job_id": 12345,
    "project": "ART",
    "ref": 1.0,
    "files": [
      "local_dir/foo.txt",
      "local_dir/bar.txt",
      "foobar.txt"
    ]
  },
]
```

## File locations

`art` uses [appdirs](https://github.com/ActiveState/appdirs) to store configuration
and cache files. When running under CI environment, the default cache directory is
automatically set to `.art-cache` so it can be preserved across jobs.

## Bugs and limitations

* Multiple Gitlab instances are not supported (and would be non-trivial to support).
* Error handling is very rudimentary: any non-trivial exceptions simply propagate
  until Python dumps a stack trace.
* Logging could be improved.
* Format of the `artifacts.yml` file is not checked and is barely documented.
* Some breakage may occur with non-trivial use cases.
* Like with any other build system, security depends on trusting the developer
  not to do anything stupid. In particular, paths are not sanitized; with enough
  ingenuity one could probably escape the build directory and wreak havoc.
* There is no `uninstall` command. If you changed artifact versions and need to
  have a clean slate, it's highly recommended to run `git clean -dfx` (beware,
  however: any local changes to your working copy will be lost without warning).
* There are probably cleaner solutions to this problem, like using some sort of
  cross-language package manager; however, I didn't find any that would satisfy
  my needs.

## Licensing

`art` is open source software; see ``COPYING`` for amusement. Email me if the
license bothers you and I'll happily re-license under anything else under the sun.

## Author

`art` was written by Kosma Moczek &lt;kosma@kosma.pl&gt;, with bugfixes thankfully
contributed by countless good people. See `git log` for full authorship information.
