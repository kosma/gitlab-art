# -*- coding: utf-8 -*-

import requests


def quote(url):
    return requests.utils.quote(url, safe='')


class Gitlab(object):

    def __init__(self, gitlab_url, auth_header):
        self.api_url = gitlab_url + '/api/v3'
        self.headers = auth_header

    def _get(self, request, *args, **kwargs):
        r = requests.get(self.api_url + request % args, headers=self.headers, **kwargs)
        r.raise_for_status()
        return r

    def get_ref_commit(self, project, ref):
        """
        Retrieve SHA1 for given ref. Refs must be given in form of tags/name
        or branches/name.

        """
        # percent-quote the tag/branch name but not the separating slash itself
        kind, slash, name = ref.partition('/')
        ref = kind + slash + quote(name)
        r = self._get('/projects/%s/repository/%s', quote(project), ref)
        return r.json()['commit']['id']

    def get_commit_last_successful_build(self, project, commit, build_name):
        """
        Retrieve last successful build ID for given commit. Returns None if no
        such build was found.

        """
        r = self._get('/projects/%s/repository/commits/%s/builds',
                      quote(project), commit, params={'scope': 'success'})
        # make sure the builds are sorted properly
        builds = sorted(r.json(), key=lambda build: build['id'], reverse=True)
        # scan for a successful build
        for build in builds:
            if build['name'] == build_name:
                return build['id']
        # we don't raise exception to make it easier to differentiate between
        # "none found" and "something's fucked up"
        return None

    def get_artifacts_zip(self, project, build_id):
        """
        Download artifacts archive.

        """
        r = self._get('/projects/%s/builds/%s/artifacts', quote(project), build_id)
        return r.text
