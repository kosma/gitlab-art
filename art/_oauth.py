# -*- coding: utf-8 -*-

import time
from urllib.parse import urljoin

import requests

# from RFC-8628 Section 3.4
DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
DEFAULT_TIMEOUT = (5, 15)

def _check_response(response):
    """Attempt to decode an OAuth JSON response"""
    # some versions of GitLab return HTTP error status codes for non-fatal errors
    # the error detail is within the json response
    try:
        status = response.json()
    except requests.exceptions.JSONDecodeError:
        if not response.ok:
            return ({}, response.reason, "invalid API response")
        return ({}, "invalid API response", "")

    error = status.get("error", None)
    if error:
        return ({}, error, status["error_description"])

    return (status, None, None)

def _wait_for_token(gitlab_url, client_id, device_code, poll_interval):
    """
    Poll the OAuth token endpoint, waiting for the user to complete authorization
    """
    while True:
        response = requests.post(
            urljoin(gitlab_url, "/oauth/token"),
            data={
                "grant_type": DEVICE_CODE_GRANT_TYPE,
                "client_id": client_id,
                "device_code": device_code
            },
            timeout=DEFAULT_TIMEOUT,
            )

        status, error, error_description = _check_response(response)

        access_token = status.get("access_token", None)
        refresh_token = status.get("refresh_token", None)
        if access_token and refresh_token:
            return (access_token, refresh_token)

        if error == "authorization_pending":
            pass
        elif error == "slow_down":
            poll_interval += 1
        elif error_description:
            print("Authentication failed:", error_description, "({})".format(error))
            return (None, None)
        else:
            print("Authentication failed:", error)
            return (None, None)

        time.sleep(poll_interval)

def authorize(gitlab_url, client_id):
    """
    Use GitLab's Device Grant Authorization flow to obtain an API access token for the
    current user.
    """
    response = requests.post(
        urljoin(gitlab_url, "/oauth/authorize_device"),
        data={"client_id": client_id, "scope": "read_api"},
        timeout=DEFAULT_TIMEOUT,
        )

    status, error, error_description = _check_response(response)
    if not status:
        print("Authentication failed:", error)
        if error_description:
            print(error_description)
        return (None, None)

    print("Authentication is required.")
    print("Visit", status["verification_uri_complete"], "and verify this code:\n")
    print("   ", status["user_code"], "\n")

    return _wait_for_token(gitlab_url, client_id, status["device_code"], status["interval"])

def refresh(gitlab_url, client_id, refresh_token):
    """
    Updates a GitLab OAuth token using the supplied refresh token and saves the new values to
    the configuration file. A new authorization is attempted if the refresh token is not accepted.
    """
    # Skip directly to new authorization if the refresh token is invalid
    if not refresh_token:
        return authorize(gitlab_url, client_id)

    response = requests.post(
        urljoin(gitlab_url, "/oauth/token"),
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token
            },
        timeout=DEFAULT_TIMEOUT,
        )

    status, error, _ = _check_response(response)
    if not status:
        print("Authentication failed:", error)
        return authorize(gitlab_url, client_id)

    return status["access_token"], status["refresh_token"]
