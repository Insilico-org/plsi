"""Google Drive through a service account, for the clinic folders (skill panel/clinic).

A service account cannot own files, so everything lives in one Google Workspace shared drive (PLSI_CLINIC_DRIVE)
where the account (key file PLSI_DRIVE_CREDENTIALS) is a Manager, as for the Mothership. Requests go through
plsi.net; the token is signed locally (extra `drive`) and kept in memory only.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

from plsi import keys, net, references
from plsi.errors import DependencyMissing, ValidationError
from plsi.files import load_json

CREDENTIALS = "PLSI_DRIVE_CREDENTIALS"
SHARED_DRIVE = "PLSI_CLINIC_DRIVE"
REFERENCE = "google_drive"
SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER = "application/vnd.google-apps.folder"
EXPORTS = {  # Google-native files have no bytes: exported on download
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
}
ALL = {"supportsAllDrives": "true"}
JWT_HEADER = b'{"alg":"RS256","typ":"JWT"}'


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class Drive:
    def __init__(self) -> None:
        info = load_json(keys.require(CREDENTIALS))
        if not isinstance(info, dict) or info.get("type") != "service_account":
            raise ValidationError(f"{CREDENTIALS} must name a service account key file (JSON)")
        self.info, self.drive_id = info, keys.require(SHARED_DRIVE)
        self.email = str(info.get("client_email", ""))
        base = references.api_base(REFERENCE)
        self.api, self.upload_url = f"{base}/drive/v3", f"{base}/upload/drive/v3/files"
        if not str(info.get("token_uri", "https://")).startswith("https://"):
            raise ValidationError("the key file's token_uri must be https")
        self._token: tuple[str, float] | None = None

    def _bearer(self) -> dict[str, str]:
        if self._token is None or self._token[1] < time.time() + 60:
            try:
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import padding
            except ImportError:
                raise DependencyMissing("Drive needs the cryptography package", hint='pip install -e ".[drive]"') from None
            now, aud = int(time.time()), self.info.get("token_uri", "https://oauth2.googleapis.com/token")
            claims = {"iss": self.email, "scope": SCOPE, "aud": aud, "iat": now, "exp": now + 3600}
            signing = _b64(JWT_HEADER) + "." + _b64(json.dumps(claims).encode())
            key = serialization.load_pem_private_key(self.info["private_key"].encode(), password=None)
            sig = key.sign(signing.encode(), padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr,call-arg]
            body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                           "assertion": f"{signing}.{_b64(sig)}"}).encode()
            reply = net.request("POST", aud, body=body, headers={"Content-Type": "application/x-www-form-urlencoded"}).json()
            keys.hide(reply["access_token"])
            self._token = (reply["access_token"], now + int(reply.get("expires_in", 3600)))
        return {"Authorization": f"Bearer {self._token[0]}"}

    def call(self, method: str, path: str, params: dict[str, Any] | None = None, body: Any = None) -> Any:
        headers = {**self._bearer(), "Accept": "application/json"}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        text = net.request(method, f"{self.api}/{path}", params={**ALL, **(params or {})}, headers=headers, body=data).text
        return json.loads(text) if text else {}

    def about(self) -> dict[str, Any]:
        """The shared drive's name and whether this account can manage it (a Manager can delete for good)."""
        d = self.call("GET", f"drives/{self.drive_id}", {"fields": "name,capabilities(canManageMembers,canDeleteChildren)"})
        return {"name": d.get("name"), "manager": bool(d.get("capabilities", {}).get("canManageMembers"))}

    def folder(self, name: str) -> str:
        made = self.call("POST", "files", {"fields": "id"}, {"name": name, "mimeType": FOLDER, "parents": [self.drive_id]})
        return made["id"]

    def share(self, file_id: str, email: str, role: str) -> str:
        """Share with one person (Drive emails them); returns the grant's permission id, the same for that person on
        every file."""
        made = self.call("POST", f"files/{file_id}/permissions", {"sendNotificationEmail": "true", "fields": "id"},
                         {"type": "user", "role": role, "emailAddress": email})
        return made["id"]

    def direct_access(self, file_id: str) -> list[dict[str, Any]]:
        """Grants on the item itself (not the drive's members): [{type, role, id}]; never an address."""
        out, page = [], None
        while True:
            r = self.call("GET", f"files/{file_id}/permissions", {"fields": "nextPageToken,permissions(id,type,role,permissionDetails)",
                                                                   **({"pageToken": page} if page else {})})
            for p in r.get("permissions", []):
                if not all(d.get("inherited") for d in p.get("permissionDetails") or [{"inherited": False}]):
                    out.append({"type": p.get("type"), "role": p.get("role"), "id": p.get("id")})
            if not (page := r.get("nextPageToken")):
                return out

    def children(self, folder_id: str) -> list[dict[str, Any]]:
        out, page = [], None
        while True:
            r = self.call("GET", "files", {"q": f"'{folder_id}' in parents and trashed = false", "corpora": "drive",
                                           "driveId": self.drive_id, "includeItemsFromAllDrives": "true", "pageSize": "200",
                                           "fields": "nextPageToken,files(id,name,mimeType,size,md5Checksum,modifiedTime)",
                                           **({"pageToken": page} if page else {})})
            out += r.get("files", [])
            if not (page := r.get("nextPageToken")):
                return out

    def download(self, item: dict[str, Any], dest_dir: Path) -> Path:
        """Bytes into dest_dir/<file id><suffix>; Sheets and Docs are exported (CSV, PDF)."""
        mime = item.get("mimeType", "")
        if mime in EXPORTS:
            target, suffix = EXPORTS[mime]
            url = f"{self.api}/files/{item['id']}/export?" + urllib.parse.urlencode({"mimeType": target})
        elif mime.startswith("application/vnd.google-apps."):
            raise ValidationError(f"a {mime.rsplit('.', 1)[-1]} cannot be downloaded", code="DRIVE_NATIVE")
        else:
            suffix = Path(item.get("name", "")).suffix.lower()[:11]
            url = f"{self.api}/files/{item['id']}?alt=media&supportsAllDrives=true"
        return net.download(url, dest_dir / f"{item['id']}{suffix}", headers=self._bearer())

    def upload(self, folder_id: str, path: Path, name: str) -> str:
        meta = json.dumps({"name": name, "parents": [folder_id]}).encode()
        boundary = "plsi" + base64.b16encode(path.name.encode()[:8]).decode() + str(int(time.time()))
        body = b"".join([f"--{boundary}\r\nContent-Type: application/json\r\n\r\n".encode(), meta,
                         f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode(), path.read_bytes(),
                         f"\r\n--{boundary}--\r\n".encode()])
        r = net.request("POST", self.upload_url, params={"uploadType": "multipart", **ALL, "fields": "id"}, body=body,
                        headers={**self._bearer(), "Content-Type": f"multipart/related; boundary={boundary}"})
        return json.loads(r.text)["id"]


def reachable() -> bool:
    """Both Drive variables are set (no network)."""
    return all(keys.get(k) for k in (CREDENTIALS, SHARED_DRIVE))

