#!/usr/bin/env python3
"""
LinkedIn publishing — deliberately gated.

  python3 tools/linkedin.py auth            one-time OAuth, stores a token
  python3 tools/linkedin.py whoami          check the token is still alive
  python3 tools/linkedin.py preview <slug>  print the exact payload, post nothing
  python3 tools/linkedin.py post <slug>     post, after you type the slug back

Nothing here posts on a schedule, on import, or without a confirmation typed
at the keyboard. `preview` is always safe.

Setup (free, ~5 minutes):
  1. https://www.linkedin.com/developers/apps  ->  Create app
     It must be linked to a LinkedIn Page you admin. A page for yourself is fine.
  2. Products tab -> request "Share on LinkedIn" and
     "Sign In with LinkedIn using OpenID Connect". Both are self-serve.
  3. Auth tab -> add redirect URL:  http://localhost:8000/callback
  4. Copy Client ID + Client Secret into tools/.env  (see .env.example)
  5. python3 tools/linkedin.py auth

Tokens last 60 days. When one expires, run `auth` again.
"""

import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
OUTBOX = ROOT / "outbox"
ENV_FILE = TOOLS / ".env"
TOKEN_FILE = TOOLS / ".linkedin_token.json"

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
API_VERSION = "202401"
SCOPES = "openid profile w_member_social"

MAX_CHARS = 3000

# The Posts API treats these as markup delimiters in `commentary`.
# '#' is left alone so hashtags still resolve.
RESERVED = r'\<>@[]()~_|{}*'


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"\'')
    return env


def die(msg, code=1):
    print(f'\n  {msg}\n', file=sys.stderr)
    sys.exit(code)


def request(url, data=None, headers=None, method=None):
    body = None
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
    elif isinstance(data, (bytes, str)):
        body = data.encode() if isinstance(data, str) else data

    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode('utf-8', 'replace')
            return r.status, dict(r.headers), (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as err:
        raw = err.read().decode('utf-8', 'replace')
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {'raw': raw}
        return err.code, dict(err.headers), parsed


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

class Callback(BaseHTTPRequestHandler):
    code = None
    state = None

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        Callback.code = (query.get('code') or [None])[0]
        Callback.state = (query.get('state') or [None])[0]
        err = (query.get('error_description') or query.get('error') or [None])[0]

        ok = Callback.code is not None
        msg = 'Authorised. Close this tab and return to the terminal.' if ok else f'Failed: {err}'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(
            f'<body style="font:16px system-ui;padding:60px;background:#080807;color:#E8E8E3">'
            f'<p>{msg}</p></body>'.encode())

    def log_message(self, *_):
        pass


def cmd_auth():
    env = load_env()
    cid = env.get('LINKEDIN_CLIENT_ID')
    secret = env.get('LINKEDIN_CLIENT_SECRET')
    redirect = env.get('LINKEDIN_REDIRECT_URI', 'http://localhost:8000/callback')

    if not cid or not secret:
        die(f'Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in {ENV_FILE}\n'
            f'  Copy tools/.env.example to tools/.env first.')

    state = secrets.token_urlsafe(16)
    url = AUTH_URL + '?' + urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': cid,
        'redirect_uri': redirect,
        'state': state,
        'scope': SCOPES,
    })

    port = urllib.parse.urlparse(redirect).port or 80
    server = HTTPServer(('localhost', port), Callback)

    print('\n  Opening LinkedIn authorisation in your browser.')
    print('  If it does not open, paste this:\n')
    print(f'  {url}\n')
    webbrowser.open(url)
    print(f'  Waiting on {redirect} ...')
    server.handle_request()
    server.server_close()

    if not Callback.code:
        die('No authorisation code came back. Check the redirect URL '
            'registered on the app matches exactly.')
    if Callback.state != state:
        die('State mismatch — aborting.')

    status, _, tok = request(TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': Callback.code,
        'client_id': cid,
        'client_secret': secret,
        'redirect_uri': redirect,
    }, headers={'Content-Type': 'application/x-www-form-urlencoded'})

    if status != 200 or 'access_token' not in tok:
        die(f'Token exchange failed ({status}): {json.dumps(tok, indent=2)}')

    status, _, who = request(USERINFO_URL,
                             headers={'Authorization': f"Bearer {tok['access_token']}"})
    if status != 200 or 'sub' not in who:
        die(f'Could not read your profile ({status}): {json.dumps(who, indent=2)}\n'
            f'  Is "Sign In with LinkedIn using OpenID Connect" added on the Products tab?')

    TOKEN_FILE.write_text(json.dumps({
        'access_token': tok['access_token'],
        'expires_in': tok.get('expires_in'),
        'sub': who['sub'],
        'name': who.get('name', ''),
    }, indent=2), encoding='utf-8')
    TOKEN_FILE.chmod(0o600)

    days = round(tok.get('expires_in', 0) / 86400)
    print(f"\n  Authorised as {who.get('name', who['sub'])}")
    print(f'  Token stored in {TOKEN_FILE.relative_to(ROOT)} — valid ~{days} days.\n')


def load_token():
    if not TOKEN_FILE.exists():
        die('No token yet. Run:  python3 tools/linkedin.py auth')
    return json.loads(TOKEN_FILE.read_text(encoding='utf-8'))


def cmd_whoami():
    tok = load_token()
    status, _, who = request(USERINFO_URL,
                             headers={'Authorization': f"Bearer {tok['access_token']}"})
    if status != 200:
        die(f'Token rejected ({status}). Run `auth` again — they expire after 60 days.\n'
            f'  {json.dumps(who)}')
    print(f"\n  Token valid. Posting as: {who.get('name', who.get('sub'))}\n")


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------

def escape_commentary(text):
    return re.sub(r'([' + re.escape(RESERVED) + r'])', r'\\\1', text)


def read_draft(slug):
    path = OUTBOX / f'{slug}.txt'
    if not path.exists():
        available = sorted(p.stem for p in OUTBOX.glob('*.txt'))
        die(f'No draft at outbox/{slug}.txt\n'
            f"  Available: {', '.join(available) or '(none — run tools/build.py)'}")
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        die(f'outbox/{slug}.txt is empty.')
    return text


def build_payload(slug, text, sub):
    """A link post if the draft ends in a bare URL, otherwise plain text."""
    link = None
    lines = text.rstrip().split('\n')
    if lines and re.fullmatch(r'https?://\S+', lines[-1].strip()):
        link = lines[-1].strip()

    payload = {
        'author': f'urn:li:person:{sub}',
        'commentary': escape_commentary(text),
        'visibility': 'PUBLIC',
        'distribution': {
            'feedDistribution': 'MAIN_FEED',
            'targetEntities': [],
            'thirdPartyDistributionChannels': [],
        },
        'lifecycleState': 'PUBLISHED',
        'isReshareDisabledByAuthor': False,
    }
    if link:
        payload['content'] = {'article': {'source': link, 'title': slug.replace('-', ' ').title()}}
    return payload, link


def show(slug, text, payload, link):
    print('\n' + '=' * 68)
    print(f'  LINKEDIN DRAFT — {slug}')
    print('=' * 68)
    print(text)
    print('=' * 68)
    print(f'  {len(text)} / {MAX_CHARS} characters'
          + ('  ** OVER LIMIT **' if len(text) > MAX_CHARS else ''))
    print(f"  Link card: {link or 'none (plain text post)'}")
    print(f"  Visibility: PUBLIC — visible to anyone on LinkedIn")
    print('=' * 68 + '\n')


def cmd_preview(slug):
    tok = TOKEN_FILE.exists() and json.loads(TOKEN_FILE.read_text()) or {'sub': 'NOT-AUTHED'}
    text = read_draft(slug)
    payload, link = build_payload(slug, text, tok.get('sub', 'NOT-AUTHED'))
    show(slug, text, payload, link)
    print('  Payload that would be sent:\n')
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print('\n  Nothing was posted. `preview` never posts.\n')


def cmd_post(slug):
    tok = load_token()
    text = read_draft(slug)
    payload, link = build_payload(slug, text, tok['sub'])

    if len(text) > MAX_CHARS:
        die(f'Draft is {len(text)} chars; LinkedIn caps a post at {MAX_CHARS}. Trim it first.')

    show(slug, text, payload, link)
    print('  This publishes to your real LinkedIn feed and cannot be undone')
    print('  from here. To confirm, type the slug exactly. Anything else aborts.\n')
    try:
        typed = input(f'  Type "{slug}" to publish: ').strip()
    except (EOFError, KeyboardInterrupt):
        die('Aborted — nothing posted.', code=0)

    if typed != slug:
        die('Aborted — nothing posted.', code=0)

    status, headers, resp = request(
        POSTS_URL,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Authorization': f"Bearer {tok['access_token']}",
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': API_VERSION,
        },
        method='POST')

    if status in (200, 201):
        urn = headers.get('x-restli-id') or resp.get('id', '')
        print(f'\n  Posted. {urn}')
        if urn:
            print(f'  https://www.linkedin.com/feed/update/{urn}/')
        posted = OUTBOX / 'posted'
        posted.mkdir(exist_ok=True)
        (posted / f'{slug}.txt').write_text(text, encoding='utf-8')
        (OUTBOX / f'{slug}.txt').unlink()
        print(f'  Draft moved to outbox/posted/{slug}.txt\n')
    else:
        die(f'LinkedIn refused the post ({status}):\n'
            f'  {json.dumps(resp, indent=2, ensure_ascii=False)}')


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ''

    if cmd == 'auth':
        cmd_auth()
    elif cmd == 'whoami':
        cmd_whoami()
    elif cmd in ('preview', 'post'):
        if len(args) < 2:
            die(f'Usage: python3 tools/linkedin.py {cmd} <slug>')
        (cmd_preview if cmd == 'preview' else cmd_post)(args[1])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
