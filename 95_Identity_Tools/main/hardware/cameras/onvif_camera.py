"""
File: hardware/cameras/onvif_camera.py

Purpose
-------
A CameraBase implementation of the ONVIF protocol -- a published,
vendor-neutral standard for IP camera interoperability (Axis, Hikvision, Dahua,
and most budget IP cameras). This module owns every piece of ONVIF protocol
logic BrisartIdentityTools needs: WS-Security UsernameToken digest generation,
SOAP envelope construction, GetCapabilities/GetProfiles/GetSnapshotUri/
GetSystemDateAndTime request bodies, XML response parsing, and translation of
transport-level failures into this project's own exception hierarchy.

Public interface:
- class ONVIFCamera(CameraBase) -- A CameraBase adapter implementing the ONVIF
  protocol. Owns all SOAP/XML/WS-Security logic; owns zero network
  connectivity. Every network operation is delegated to a required,
  caller-supplied hardware.base.onvif_transport.ONVIFTransport instance. Public
  methods: name, connect, disconnect, health_check, capture_image.

Design notes:

All of it is implemented with Python's standard library only (hashlib, base64,
os, datetime, xml.etree.ElementTree) -- zero third-party packages. This module
deliberately does NOT open a network connection. The one operation it cannot do
without leaving pure protocol logic -- actually sending bytes to the camera and
getting bytes back -- is delegated to a
hardware.base.onvif_transport.ONVIFTransport instance supplied by the caller at
construction time. This project ships the transport contract
(hardware/base/onvif_transport.py) but no implementation of it, mirroring the
same boundary hardware/base/pcsc_binding.py already draws for smart-card
readers. See hardware/README.md, "Why the ONVIF transport is not shipped," for
the full reasoning.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.camera_base (hardware/base/camera_base.py)
- hardware.base.onvif_transport (hardware/base/onvif_transport.py)
- hardware.exceptions (hardware/exceptions.py)
Standard library: base64, datetime, hashlib, os, xml.
Imported by: no other module in this tree imports it directly.
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- DEFAULT_PORT = 80
- _SOAP_NAMESPACES -- XML namespace map used to build and read ONVIF messages:
  soap (SOAP 1.2 envelope), wsse and wsu (WS-Security secext and utility), tds
  (ONVIF device service), trt (ONVIF media service), and tt (ONVIF schema).

Edge cases
----------
- ONVIFCamera.__init__() raises TypeError: "ONVIFCamera requires a
  hardware.base.onvif_transport.ONVIFTransport instance; got {...} instead.
  This project ships the transport CONTRACT only -- see hardware/README.md,
  'Why the ONVIF transport is not shipped,' for how to supply one."
- ONVIFCamera._post_soap() raises DeviceConnectionError: "SOAP request to {...}
  failed: {...}"
- ONVIFCamera._post_soap() raises DeviceConnectionError: "malformed SOAP
  response from {...}: {...}"
- ONVIFCamera._discover_media_service_url() raises DeviceConnectionError:
  "{...} did not advertise a Media service address in GetCapabilities."
- ONVIFCamera._get_first_profile_token() raises DeviceConnectionError: "{...}
  reported zero ONVIF media profiles."
- ONVIFCamera._get_snapshot_uri() raises DeviceConnectionError: "{...} did not
  return a snapshot URI for profile {...}."
- ONVIFCamera.capture_image() raises DeviceConnectionError: "{...} is not
  connected; call connect() first."
- ONVIFCamera.capture_image() raises DeviceConnectionError: "snapshot fetch
  from {...} failed: {...}"
- ONVIFCamera._post_soap(): translates ElementTree.ParseError into
  DeviceConnectionError, so callers only need to handle this module's own error
  type.
- ONVIFCamera._post_soap(), ONVIFCamera.capture_image(): translates
  ONVIFTransportError into DeviceConnectionError, so callers only need to
  handle this module's own error type.
- ONVIFCamera.connect(), ONVIFCamera.health_check(): catches
  DeviceConnectionError and handles it in place; it does not propagate to the
  caller.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
Call shapes only, not a runnable script: transport, host, username, password
stand for values the caller supplies.

::

    from hardware.cameras.onvif_camera import ONVIFCamera
    obj = ONVIFCamera(transport, host, username, password)
    obj.name
"""

import base64
import hashlib
import os
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone

from hardware.base.camera_base import CameraBase
from hardware.base.onvif_transport import ONVIFTransport, ONVIFTransportError
from hardware.exceptions import DeviceConnectionError

DEFAULT_PORT = 80

_SOAP_NAMESPACES = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/"
            "oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "wsu": "http://docs.oasis-open.org/wss/2004/01/"
           "oasis-200401-wss-wssecurity-utility-1.0.xsd",
    "tds": "http://www.onvif.org/ver10/device/wsdl",
    "trt": "http://www.onvif.org/ver10/media/wsdl",
    "tt": "http://www.onvif.org/ver10/schema",
}
for _prefix, _uri in _SOAP_NAMESPACES.items():
    ElementTree.register_namespace(_prefix, _uri)


def _ws_security_header(username: str, password: str) -> str:
    """Build a WS-Security UsernameToken header using PasswordDigest,
    per the ONVIF/WS-Security spec: digest = Base64(SHA1(nonce +
    created + password)). A fresh nonce and timestamp are generated on
    every call.
    """
    nonce = os.urandom(16)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest = hashlib.sha1(
        nonce + created.encode("utf-8") + password.encode("utf-8")
    ).digest()
    return f"""
    <wsse:Security soap:mustUnderstand="1">
      <wsse:UsernameToken>
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/
oasis-200401-wss-username-token-profile-1.0#PasswordDigest">
          {base64.b64encode(digest).decode('ascii')}
        </wsse:Password>
        <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/
oasis-200401-wss-soap-message-security-1.0#Base64Binary">
          {base64.b64encode(nonce).decode('ascii')}
        </wsse:Nonce>
        <wsu:Created>{created}</wsu:Created>
      </wsse:UsernameToken>
    </wsse:Security>
    """


def _soap_envelope(body_xml: str, username=None, password=None) -> bytes:
    header = (
        _ws_security_header(username, password)
        if username is not None else ""
    )
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="{_SOAP_NAMESPACES['soap']}"
               xmlns:wsse="{_SOAP_NAMESPACES['wsse']}"
               xmlns:wsu="{_SOAP_NAMESPACES['wsu']}"
               xmlns:tds="{_SOAP_NAMESPACES['tds']}"
               xmlns:trt="{_SOAP_NAMESPACES['trt']}">
  <soap:Header>{header}</soap:Header>
  <soap:Body>{body_xml}</soap:Body>
</soap:Envelope>"""
    return envelope.encode("utf-8")


class ONVIFCamera(CameraBase):
    """A CameraBase adapter implementing the ONVIF protocol. Owns all
    SOAP/XML/WS-Security logic; owns zero network connectivity. Every
    network operation is delegated to a required, caller-supplied
    hardware.base.onvif_transport.ONVIFTransport instance.
    """

    def __init__(self, transport: ONVIFTransport, host, username,
                 password, port=DEFAULT_PORT):
        if not isinstance(transport, ONVIFTransport):
            raise TypeError(
                "ONVIFCamera requires a hardware.base.onvif_transport."
                "ONVIFTransport instance; got "
                f"{type(transport).__name__!r} instead. This project "
                "ships the transport CONTRACT only -- see "
                "hardware/README.md, 'Why the ONVIF transport is not "
                "shipped,' for how to supply one."
            )
        self._transport = transport
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._device_service_url = f"http://{host}:{port}/onvif/device_service"
        self._media_service_url = None
        self._snapshot_uri = None
        self.last_error = None

    @property
    def name(self) -> str:
        return f"ONVIF Camera ({self._host}:{self._port})"

    def _post_soap(self, url: str, body_xml: str,
                    username=None, password=None) -> ElementTree.Element:
        payload = _soap_envelope(body_xml, username, password)
        headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
        try:
            raw = self._transport.post(url, payload, headers)
        except ONVIFTransportError as exc:
            raise DeviceConnectionError(
                f"SOAP request to {url} failed: {exc}"
            ) from exc
        try:
            return ElementTree.fromstring(raw)
        except ElementTree.ParseError as exc:
            raise DeviceConnectionError(
                f"malformed SOAP response from {url}: {exc}"
            ) from exc

    def connect(self) -> bool:
        try:
            self._media_service_url = self._discover_media_service_url()
            token = self._get_first_profile_token()
            self._snapshot_uri = self._get_snapshot_uri(token)
            self.last_error = None
            return True
        except DeviceConnectionError as exc:
            self.last_error = exc
            self._media_service_url = None
            self._snapshot_uri = None
            return False

    def _discover_media_service_url(self) -> str:
        body = "<tds:GetCapabilities><tds:Category>Media</tds:Category></tds:GetCapabilities>"
        root = self._post_soap(
            self._device_service_url, body, self._username, self._password,
        )
        media_xaddr = root.find(".//tt:Media/tt:XAddr", _SOAP_NAMESPACES)
        if media_xaddr is None or not media_xaddr.text:
            raise DeviceConnectionError(
                f"{self._host} did not advertise a Media service "
                "address in GetCapabilities."
            )
        return media_xaddr.text.strip()

    def _get_first_profile_token(self) -> str:
        body = "<trt:GetProfiles/>"
        root = self._post_soap(
            self._media_service_url, body, self._username, self._password,
        )
        profile = root.find(".//trt:Profiles", _SOAP_NAMESPACES)
        if profile is None or "token" not in profile.attrib:
            raise DeviceConnectionError(
                f"{self._host} reported zero ONVIF media profiles."
            )
        return profile.attrib["token"]

    def _get_snapshot_uri(self, token: str) -> str:
        body = (
            f'<trt:GetSnapshotUri><trt:ProfileToken>{token}'
            f'</trt:ProfileToken></trt:GetSnapshotUri>'
        )
        root = self._post_soap(
            self._media_service_url, body, self._username, self._password,
        )
        uri_element = root.find(".//trt:Uri", _SOAP_NAMESPACES)
        if uri_element is None or not uri_element.text:
            raise DeviceConnectionError(
                f"{self._host} did not return a snapshot URI for "
                f"profile {token!r}."
            )
        return uri_element.text.strip()

    def disconnect(self) -> None:
        self._media_service_url = None
        self._snapshot_uri = None

    def health_check(self) -> bool:
        try:
            body = "<tds:GetSystemDateAndTime/>"
            self._post_soap(self._device_service_url, body)
            # unauthenticated per the ONVIF spec for this operation
            self.last_error = None
            return True
        except DeviceConnectionError as exc:
            self.last_error = exc
            return False

    def capture_image(self) -> bytes:
        if self._snapshot_uri is None:
            raise DeviceConnectionError(
                f"{self.name} is not connected; call connect() first."
            )
        headers = {"Accept": "image/jpeg"}
        try:
            return self._transport.get(
                self._snapshot_uri, headers,
                username=self._username, password=self._password,
            )
        except ONVIFTransportError as exc:
            raise DeviceConnectionError(
                f"snapshot fetch from {self._snapshot_uri} failed: {exc}"
            ) from exc




