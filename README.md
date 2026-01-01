# art - cross-project Gitlab artifact dependencies

`art` solves a burning problem of pulling artifacts from different repositories.

## Quickstart

1. Add `gitlab-art` as an [OAuth 2.0 Application in GitLab](#registering-the-gitlab-art-application)

2. Configure `art` with the GitLab url and Application ID:

    ```shell
    $ art configure https://gitlab.example.com/ --token-type oauth 5d2d3932481b8e42662091a9d3bbad8b252ea84a1e456e576939d0118d529063
    ```

3. Create `artifacts.yml` with definitions of needed artifacts:

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

4. Run `art update` to automatically determine latest versions and job numbers
   of needed projects and save them into `artifacts.lock.yml`. Commit both files
   to version control system.

5. Run `art install` to fetch required artifacts to your local cache and
   install them to the project directory.


## Continuous integration

Add the following commands to your `.gitlab-ci.yml`:

```yaml
before_script:
  - pip install gitlab-art
  - art configure <url> --token-type {private,job} <token>
  - art install
cache:
  paths:
    - .art-cache/
```

## The artifacts.yml file
The `artifacts.yml` file lists GitLab projects whose artifacts should be downloaded
and installed into the current directory.

Every project in the yaml file must include the following attributes:

|attribute|description|
|---------|-----------|
|`project`|The relative path to the project in GitLab|
|`ref`|The git tag, branch, or release version number that identifies the artifact to download|
|`source`|The type of artifact. Choices are `ci-job`, `repository`, or `generic-package`. If not specified, the default value is `ci-job`|
|`extract`|Indicates whether files from the artifact should be extracted before install. If `yes`, the default, the artifact must be a ZIP archive and the install request source paths specify files within the archive. If `no`, the install request source paths must be `'.'`, indicating the artifact file itself, and the downloaded file will be copied to the destination path|
|`install`|A list of `source_path:dest_path` install requests that identify the artifact files to be installed and their destination relative to the current directory|

### Job artifact sources
When the `source` attribute is set to `ci-job`, the default, Art downloads the ZIP
archive for the job artifacts from the latest CI/CD pipeline for the indicated `ref`.

A `ci-job` source has the following additional `artifacts.yml` attributes:
|attribute|description|
|---------|-----------|
|`job`|Specifies the name of the CI/CD job whose artifact archive will be downloaded/extracted/installed|

```yaml
- project: gitlab-org/cli
  ref: main
  source: ci-job
  job: windows_installer
  install:
    bin/glab__Windows_x86_64_installer.exe: artifacts/glab/Windows_x86_64_installer.exe
```

### Repository sources
When the `source` attribute set to `repository`, Art downloads the ZIP archive of
the repository's source tree for the indicated `ref`. The install request source
paths specify files within the git repository rather than a CI/CD job artifact.

NOTE: The repository archive created by GitLab includes a top-level folder based on the
repository hash or ref. This folder is skipped by Art when evaluating install request source
paths. The paths specified in `artifacts.yml` should be relative to the root of the repository
and not the ZIP archive.

```yaml
- project: gitlab-org/cli
  ref: main
  source: repository
  install:
    scripts/sign-binary.sh: artifacts/glab/sign-binary.sh
```

### Generic package sources
When the `source` attribute is set to `generic-package`, Art downloads a file from
GitLab's Generic Package registry. A generic package is a set of files published by
a project that are identified by a package name and a version. The package itself
contains one or more files, each identified by their filename.

A `generic-package` source has the following additional `artifacts.yml` attributes:
|attribute|description|
|---------|-----------|
|`package`|Name given to the generic package when published|
|`filename`|Name of the file within the package that should be downloaded|

To download a generic package using Art, specify the package's name in the `package`
attribute, the package's version in the `ref` attribute, and the filename to download
in the `filename` attribute.

NOTE: If the generic package is not a ZIP archive, set the `exract` attribute to `no` and
use the `'.'` value as the install request source path to install the file as-is.

```yaml
- project: gitlab-org/cli
  ref: 1.65.0
  source: generic-package
  package: glab
  filename: glab_1.65.0_windows_amd64.zip
  install:
      bin/glab.exe: artifacts/glab/windows/glab.exe
      bin/: artifacts/glab/
- project: gitlab-org/cli
  ref: 1.65.0
  source: generic-package
  package: glab
  filename: glab.exe
  # Set extract to "no" when installing a non-archive file
  extract: no
  install:
      .: artifacts/glab/
```

## The `artifacts.lock.yml` file
The `artifacts.lock.yml` is created by the `art update` command. It is
conceptually similar to Ruby's `Gemfile.lock`: it allows locking to exact
revisions and jobs while still semantically tracking tags or branches and
allowing easy updates when needs arise. The following good practices should
be followed:

* Always run `art update` after editing `artifacts.yml`.
* Always commit both files to version control.
* Do not run `art update` automatically unless you enjoy breaking the build.

The lock file itself contains the information from the `artifacts.yml` file,
with the following additional attributes.

|attribute|description|
|---------|-----------|
|`job_id`|The unique ID of the CI job containing artifacts for `ci-job` sources|
|`commit`|The git commit that corresponds to the indicated `ref` for `ci-job` or `repository` sources|
|`package_id`|The unique ID of the generic package that corresponds to the indicated `package` and `ref` for `generic-package` sources|
|`package_file_id`|The unique ID of the generic package file that corresponds to the indicated `package_id` and `filename` for `generic-package` sources|
|`files`|List of files that will be installed from the artifact into the current directory|

```yaml
- extract: false
  filename: glab.exe
  files:
  - glab.exe: artifacts/glab/glab.exe
  install:
    .: artifacts/glab/
  package: glab
  package_file_id: 215807881
  package_id: 43329768
  project: gitlab-org/cli
  ref: 1.65.0
  source: generic-package
- filename: glab_1.65.0_windows_amd64.zip
  files:
  - bin/glab.exe: artifacts/glab/windows/glab.exe
  - bin/glab.exe: artifacts/glab/glab.exe
  install:
    bin/: artifacts/glab/
    bin/glab.exe: artifacts/glab/windows/glab.exe
  package: glab
  package_file_id: 215807851
  package_id: 43329768
  project: gitlab-org/cli
  ref: 1.65.0
  source: generic-package
```

## Changing the working directory
The `art update` command looks for an `artifacts.yml` file in the current directory, and
the `art install` command installs files relative to this directory. This can be changed
using the top-level `-C, --change-dir DIR` option which changes the current directory
prior to running the `update` or `install` command.
```shell
$ art -C ./dependencies/ update
```

Example updating and installing artifacts into a "deps" directory:
```yaml
$ cat deps/artifacts.yml 
- project: gitlab-org/cli
  ref: main
  source: ci-job
  job: windows_installer
  install:
    bin/glab__Windows_x86_64_installer.exe: glab/Windows_x86_64_installer.exe
````

```
$ art -C deps update
* gitlab-org/cli: main => 12573823854

$ art -C deps install
* install: bin/glab__Windows_x86_64_installer.exe => glab/Windows_x86_64_installer.exe   -rwxr-xr-x

$ tree deps
deps
├── artifacts.lock.yml
├── artifacts.yml
└── glab
    └── Windows_x86_64_installer.exe

2 directories, 3 files
```

## Using a different filename for `artifacts.yml`
Art manages the artifacts for the projects listed in the file `artifacts.yml`. The
top-level `-f, --file FILE` option can be used to specify a different artifacts file 
for the `update` or `install` commands.

When combined with the `-C, -change-dir DIR` option, the directory is changed before
the artifacts file path is resolved.

```
$ art -f artifacts/prod/deps.prod.yml update
* gitlab-org/cli: main => 12573823854

$ tree artifacts/prod
artifacts/prod
├── deps.prod.lock.yml
└── deps.prod.yml

1 directory, 2 files
```

## Authentication
Art uses API tokens to authenticate with GitLab. There are three
different token types available. The `-t, --token-type` option of `art configure` can be
used to specify the authentication method to use based on the type of token that
is available.

```yaml
   $ art configure https://gitlab.com --token-type private abc1234
```

As of `art v0.5.0`, the recommended token type for use outside of CI/CD pipelines is `oauth`.

### Private tokens
A private token allows Art to access the GitLab API using your user account. Private tokens
can be created from the "Personal access tokens" menu of your GitLab user profile. When
creating a token for Art, the scope option should be set to `read_api`. This limits the 
granted permissions to only those required to find and download artifacts.

A disadvantage of private tokens is that they require an expiration date, can't be issued
for more than 1 year, and can't be renewed using the API.

### Job tokens
The `job` token type is a temporary credential issued by GitLab during the lifetime of a CI/CD pipeline. They
are only available to Art when it is executing within the context of a CI/CD job. This token
type uses the value in the `$CI_JOB_TOKEN` CI variable to obtain a token with a
portion of the permissions assigned to the user that ran the pipeline.

```
$ art configure --token-type job $CI_JOB_TOKEN
```

Starting in GitLab 15.9, new [job token security settings](https://about.gitlab.com/releases/2023/02/22/gitlab-15-9-released/#control-which-projects-can-access-your-project-with-a-cicd-job-token)
have been introduced that require explicit authorization to access a project using
a CI job token. This is intended to prevent malicious pipelines from having full download
access to all projects accessible to the user running the pipeline. Extra steps will be
required to ensure the CI/CD pipeline that executes `art` has the required project
permissions.

NOTE: A [job token does not have access](https://docs.gitlab.com/ci/jobs/ci_job_token/#job-token-access)
 to the `pipeline` and `job` endpoints required to run the `art update` command. When installing 
artifacts from a CI/CD job, commit the `artifacts.lock.yml` file to version control and only use the
`art configure` and `art install` commands.

### OAuth device tokens
The `oauth` token type uses a local web browser to authorize Art's access to your GitLab user account
using the OAuth device authorization grant [introduced in GitLab 17.2](https://about.gitlab.com/releases/2024/07/18/gitlab-17-2-released/#oauth-20-device-authorization-grant-support).

Using an OAuth link reduces the steps required to issue and manage private tokens, and enables the use of
two-factor authentication when granting permission.

#### Registering the gitlab-art application
To use OAuth tokens, Art must be added as an Application within GitLab at the User, Group,
or Instance level. For details, see the [Gitlab OAuth 2.0 Identity Provider](https://docs.gitlab.com/integration/oauth_provider/)
instructions.

- For "Name", specify a user-recognizable name like "gitlab-art"
- For "Callback Url", provide a non-existant HTTPS url, like "https://device.grant.has.no.callback.url/"
  - This callback url is used by different types of OAuth grant. GitLab's form validation requires
    a valid url, but the value provided will not be used.
- For "Scope", check only the `read_api` option

After saving the Application, publish the "Application ID" value for users to use as
the token value in the `art configure` command:

```
$ art configure --token-type oauth https://gitlab.com/ APPLICATION_ID
```

```
$ art configure --token-type oauth https://gitlab.com/ 5d2d3932481b8e42662091a9d3bbad8b252ea84a1e456e576939d0118d529063
Authentication is required.
Visit https://gitlab.com/oauth/device?user_code=0B3H0YMB and verify this code:

    0B3H0YMB 
```

OAuth tokens expire, similar to private tokens, and can be revoked using the "Applications"
tab of your user profile settings. If a token has expired, but is not revoked, Art will 
refresh the token using its previous credential. If unsuccessful, an authentication prompt
will be displayed with a link to generate a new token.

## Structured output options
The `art update` and `art install` commands include a `-j, --json` option that
prints the command result to standard output in JSON format. This
is a machine-readable format that can be used by build systems or other utilities
to process the list of installed files and their metadata.

The fields in the JSON output includes the values in the `artifacts.lock.yml` file.

A simple example output is below

```bash
$ art install --json
[
  {
    "commit": "afd2807c9ab477c97e0d807fb73121848c625ec1",
    "filename": "artifacts.zip",
    "files": [
      { "bin/glab__Windows_x86_64_installer.exe": "artifacts/glab/Windows_x86_64_installer.exe" }
    ],
    "install": {
      "bin/glab__Windows_x86_64_installer.exe": "artifacts/glab/Windows_x86_64_installer.exe"
    },
    "job": "windows_installer",
    "job_id": 12573823854,
    "project": "gitlab-org/cli",
    "ref": "main",
    "source": "ci-job"
  }
]
```

## File locations
`art` uses [platformdirs](https://github.com/tox-dev/platformdirs) to store configuration
and cache files. When running under CI environment, the default cache directory is
automatically set to `.art-cache` so it can be preserved across jobs.

### Cache management
Files downloaded by Art can be managed using the `art cache` command.

```
$ art cache --help
Usage: python -m art cache [OPTIONS] COMMAND [ARGS]...

  Inspect and manage the artifact cache

Commands:
  list   List projects with cached artifacts and their size
  purge  Remove cached artifacts.
```

The `list` command displays the disk spaced used for each project that has
previously cached artifacts.

The `purge` command removes artificts from one, several, or all projects.
Multiple projects can be selected using shell-style wildcard patterns.

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
