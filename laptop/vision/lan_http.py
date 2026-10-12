from __future__ import annotations

"""HTTP helpers for camera sources on a trusted local network.

Redirects are deliberately disabled so a private camera URL cannot redirect the
laptop to an unrelated host or public endpoint.
"""

from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_no_redirect(request: Request, *, timeout: float):
    """Open one HTTP request without following redirects."""
    return build_opener(_NoRedirectHandler()).open(request, timeout=timeout)
