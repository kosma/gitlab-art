# art - Gitlab artifact repository client

`art` solves a burning problem of pulling artifacts from different repositories
into the build while keeping the system secure and clean.

## Quickstart

1. Create a Gitlab private token and save it in `art` configuration:

    ```shell
    art config https://gitlab.example.com/ 'as1!df2@gh3#jk4$'
    ```

   This only needs to be done once per your developer machine.

2. Create `artifacts.yml` with definitions of needed artifacts:

    ```yaml
    - project: kosma/foobar-documentation
      ref: branches/stable
      build: doc
      install:
        build/apidoc/html: docs/api/
        VERSION: docs/VERSION/
    - project: kosma/foobar-firmware
      ref: tags/1.4.0
      build: firmware-8051
      install:
        build/8051/release/firmware.bin: blogs/firmware-8051.blob
    - project: kosma/foobar-icons
      ref: 69881ebc852f5e02b8328c6b9da615e90b7184b2
      build: icons
      install:
        .: icons/
    ```

3. Run `art update` to automatically determine latest versions and build numbers
   of needed projects and save them into `artifacts.lock.yml`. Commit both files
   to version control system.

4. Run `art download` to fetch required artifacts to your local cache and
   `art install` to install them to the project directory.

## The Lockfile

The `artifacts.lock.yml` is conceptually similar to Ruby's `Gemfile.lock`: it
allows locking to exact revisions and builds while still semantically tracking
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
  - art download
  - art install
cache:
  paths:
    - .art-cache/
```

`art` uses Gitlab's `$CI_BUILD_TOKEN` infrastructure to automatically gain access
to needed build artifacts. Your private token is never transmitted to the CI system.

## File locations

`art` uses [appdirs](https://github.com/ActiveState/appdirs) to store configuration
and cache files. When running under CI environment, the default cache directory is
automatically set to `.art-cache` so it can be preserved across builds.

## Licensing

`art` is open source software; see ``COPYING`` for amusement. Email me if the
license bothers you and I'll happily re-license under anything else under the sun.

## Author

`art` was written by Kosma Moczek &lt;kosma@kosma.pl&gt;, with bugfixes thankfully
contributed by countless good people. See `git log` for full authorship information.
