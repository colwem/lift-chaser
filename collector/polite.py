"""Slow, honest HTTP for the collectors.

Rules (see docs/glider-flights-plan.md): identify ourselves truthfully, keep a gap between
requests to the same host, and never work around a block. A 403 or 429 means the site said no:
we raise Blocked and the run stops for that source; nothing retries it or changes identity.
"""
import json, time, urllib.error, urllib.parse, urllib.request

UA = "chase-lift/0.3 (personal soaring research; slow collector)"

class Blocked(Exception):
    pass

class Polite:
    def __init__(self, source, min_gap_s, log=None, opener=None):
        # opener: a urllib opener with a cookie jar, for sources where we keep a logged-in session
        self.source, self.gap, self.log, self.last, self.opener = source, min_gap_s, log, 0.0, opener

    def post_form(self, url, fields, tries=1):
        """POST an HTML form (application/x-www-form-urlencoded), as a browser's login form does."""
        return self.get(url, tries, data=urllib.parse.urlencode(fields).encode(),
                        headers={"Content-Type": "application/x-www-form-urlencoded"})

    def post_json(self, url, body, accept="application/json", tries=3):
        """POST a JSON body, as a site's own page does for its data requests."""
        return self.get(url, tries, data=json.dumps(body).encode(),
                        headers={"Accept": accept, "Content-Type": "application/json"})

    def get(self, url, tries=3, data=None, headers=None):
        for attempt in range(tries):
            wait = self.last + self.gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
                with (self.opener.open if self.opener else urllib.request.urlopen)(req, timeout=90) as r:
                    body = r.read()
                    if self.log: self.log(self.source, url, r.status, len(body))
                    return body
            except urllib.error.HTTPError as e:
                if self.log: self.log(self.source, url, e.code, 0)
                if e.code in (401, 403, 429):
                    raise Blocked(f"{self.source}: HTTP {e.code} for {url}; stopping this source")
                if e.code == 404 or attempt == tries - 1:
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == tries - 1:
                    raise
            time.sleep(30 * (attempt + 1))   # server trouble (5xx, timeouts): back off, then try again
