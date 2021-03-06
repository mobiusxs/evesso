import base64
import hashlib
import secrets
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from .const import AUTH_URL, TOKEN_URL, HEADERS
from .callback import listen_for_callback

STATE = secrets.token_urlsafe(32)


def generate_byte_string(length: int = 32) -> bytes:
    """Create a base64-encoded random byte string containing *nbytes* bytes

    Example output:

        b'RQWLR1FETAc7aKTyY11TUloY4ZMN9NCMbalu136UaJ0='

    :param length: int length in bytes
    :return: bytes random byte string
    """

    return base64.urlsafe_b64encode(secrets.token_bytes(length))


def generate_challenge(verifier: bytes) -> str:
    """Create url-safe code challenge from the verifier

    Example output:

        'BN0U4BFRvGVfghY4fE41bCBME66lrFaDNS7NUPpOtZg'

    :param verifier: bytes random byte string
    :return: str url-safe string to be used as challenge for integrity verification
    """

    m = hashlib.sha256()
    m.update(verifier)
    d = m.digest()
    return base64.urlsafe_b64encode(d).decode().replace("=", "")


def build_auth_url(client_id: str, scope, callback_url: str, code_verifier: bytes) -> str:
    """Construct an authorization url containing required details.
    The url is used for the user to grant access to the application.

    :param client_id: str Client ID associated with your application, found at https://developers.eveonline.com/applications
    :param scope: str a space-delimited string of scopes, found at https://developers.eveonline.com/applications
    :param callback_url: str path to accept callback from auth server, found at https://developers.eveonline.com/applications. Default and recommended value is https://localhost/callback/
    :param code_verifier: bytes random byte string
    :return: str authorization url
    """

    query_string = {
        'response_type': 'code',
        'redirect_uri': callback_url,
        'client_id': client_id,
        'scope': scope,
        'code_challenge': generate_challenge(code_verifier),
        'code_challenge_method': 'S256',
        'state': STATE
    }
    return f'{AUTH_URL}?{urlencode(query_string)}'


def parse_callback_url(callback_url: str) -> dict:
    """Extract the requested url path and parse it.
    Return the parsed query string as a dict with the
    structure of `{str: list}`.

    Example output:
        {'code': ['abdcefghijklmnopqrstuvwxyz0123456789'], 'state': ['secret']}

    :return: dict query string parameters from the callback
    """

    parsed_path = urlparse(callback_url)
    return parse_qs(parsed_path.query)


def get_auth_jwt(client_id: str, scope: str, callback_url: str, cli: bool) -> dict:
    """Open browser to auth URL for user to authorize the app.
    Receive the callback and parse the code and state values.
    Use the received code value to send request for access token.

    :param client_id: str Client ID associated with your application, found at https://developers.eveonline.com/applications
    :param scope: str a space-delimited string of scopes, found at https://developers.eveonline.com/applications
    :param callback_url: str path to accept callback from auth server, found at https://developers.eveonline.com/applications. Default and recommended value is https://localhost/callback/
    :return: dict JWT received from authorization server containing access token and refresh token
    :param cli: bool use command line interface for authorization
    """

    code_verifier = generate_byte_string()
    auth_url = build_auth_url(client_id, scope, callback_url, code_verifier)
    if cli:
        print(f'Open this url in a web browser:\n\n{auth_url}\n\n')
        callback = input('Copy the callback URL from your web browser and paste it here, then press enter:\n')
    else:
        webbrowser.open(auth_url)
        callback = listen_for_callback()
    query_string = parse_callback_url(callback)
    code = query_string.get('code')[0]
    state = query_string.get('state')[0]

    if not state == STATE:
        raise ValueError('Did not receive expected state')

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": code_verifier
    }
    response = requests.post(TOKEN_URL, data=data, headers=HEADERS)
    response.raise_for_status()
    jwt = response.json()
    return jwt
