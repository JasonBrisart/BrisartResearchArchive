"""
File: hardware/base/onvif_transport.py

Purpose
-------
Defines the contract for the ONE operation this project deliberately does not
implement for ONVIF cameras: opening a network connection and exchanging bytes
with the camera itself. Every other piece of ONVIF logic -- SOAP envelope
construction, WS-Security UsernameToken digest generation, XML response
parsing, capability/profile selection, snapshot-URI resolution, and error
translation -- is implemented in pure Python, with zero network calls, in
hardware/cameras/onvif_camera.py, and needs no transport at all to exercise
that logic in isolation.

Public interface:
- class ONVIFTransportError(Exception) -- Raised by an ONVIFTransport
  implementation for any low-level network failure (connection refused, DNS
  failure, TLS failure, timeout, non-2xx HTTP status, or any other
  transport-level error). onvif_camera.py catches this exception type
  specifically and translates it into DeviceConnectionError.
- class ONVIFTransport(ABC) -- The raw network operations
  hardware/cameras/onvif_camera.py needs. An implementation of this class is
  the only place in a deployment of BrisartIdentityTools where a network
  connection to an ONVIF camera is actually opened. This project ships no
  implementation of this class -- see hardware/README.md. Public methods: post,
  get.

Design notes:

An ONVIFTransport implementation is the one piece of code in this project's
camera support path that must open a socket, perform an HTTP request, and talk
to a physical network endpoint. This project ships the CONTRACT only.
Implementing it -- actually calling urllib, a proxy-aware HTTP client, an
organization's camera gateway, or any other network mechanism -- is left to the
organization deploying this software, under their own network and audit
posture. See hardware/README.md, "Why the ONVIF transport is not shipped," for
the full reasoning. This mirrors, deliberately, the same boundary
hardware/base/pcsc_binding.py already draws for smart-card readers.

Communication / relationships
-----------------------------
Standard library: abc.
Imported by:
- hardware/cameras/onvif_camera.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.base.onvif_transport import ONVIFTransport
    obj = ONVIFTransport()
    obj.post(url, body, headers)
"""

from abc import ABC, abstractmethod


class ONVIFTransportError(Exception):
    """Raised by an ONVIFTransport implementation for any low-level
    network failure (connection refused, DNS failure, TLS failure,
    timeout, non-2xx HTTP status, or any other transport-level error).
    onvif_camera.py catches this exception type specifically and
    translates it into DeviceConnectionError."""


class ONVIFTransport(ABC):
    """The raw network operations hardware/cameras/onvif_camera.py
    needs. An implementation of this class is the only place in a
    deployment of BrisartIdentityTools where a network connection to
    an ONVIF camera is actually opened. This project ships no
    implementation of this class -- see hardware/README.md.
    """

    @abstractmethod
    def post(self, url: str, body: bytes, headers: dict) -> bytes:
        """Send `body` to `url` as an HTTP POST with the given headers
        and return the FULL raw response body as bytes. Raise
        ONVIFTransportError on any failure (connection, timeout, TLS,
        non-2xx status, or otherwise)."""

    @abstractmethod
    def get(self, url: str, headers: dict, username: str = None,
            password: str = None) -> bytes:
        """Retrieve `url` as an HTTP GET with the given headers and
        return the FULL raw response body as bytes. Raise
        ONVIFTransportError on any failure.

        `username`/`password` are passed explicitly (rather than
        pre-encoded into `headers`) because real ONVIF cameras are
        inconsistent about whether their snapshot endpoint expects HTTP
        Basic or HTTP Digest authentication, and negotiating that
        (a Digest challenge/response round trip, in particular)
        requires the transport to hold the raw credentials, not a
        single pre-committed Authorization header value. Used by
        ONVIFCamera to retrieve snapshot bytes from a camera-provided
        snapshot URI."""




