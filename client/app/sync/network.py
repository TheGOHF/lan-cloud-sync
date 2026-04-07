from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
import hashlib
from pathlib import Path
from uuid import uuid4

import requests
from requests import Response
from requests import Session
from requests.exceptions import RequestException

from .config import ClientConfig, get_client_config
from .file_utils import iter_file_chunks
from shared.schemas import DeleteFileResponse, FileMetadataResponse, UploadFileResponse


class NetworkError(RuntimeError):
    pass


def get_files(
    updated_since: datetime | None = None,
    *,
    config: ClientConfig | None = None,
) -> list[FileMetadataResponse]:
    params: dict[str, str] | None = None
    if updated_since is not None:
        params = {"updated_since": updated_since.isoformat()}

    response = _request("GET", "/files", config=config, params=params)
    payload = response.json()
    return [FileMetadataResponse.model_validate(item) for item in payload]


def upload_file(
    local_path: Path,
    remote_path: str,
    device_id: str,
    *,
    config: ClientConfig | None = None,
) -> UploadFileResponse:
    resolved_config = config or get_client_config()
    boundary = f"lancloudsync-{uuid4().hex}"
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    stream = MultipartUploadStream(
        local_path=local_path,
        remote_path=remote_path,
        device_id=device_id,
        boundary=boundary,
        chunk_size=resolved_config.chunk_size,
    )
    response = _request("POST", "/upload", config=resolved_config, data=stream, headers=headers)
    return UploadFileResponse.model_validate(response.json())


def download_file(remote_path: str, local_path: Path, *, config: ClientConfig | None = None) -> None:
    resolved_config = config or get_client_config()
    local_path.parent.mkdir(parents=True, exist_ok=True)

    response = _request(
        "GET",
        "/download",
        config=resolved_config,
        params={"path": remote_path},
        stream=True,
    )

    with local_path.open("wb") as file_obj:
        for chunk in response.iter_content(chunk_size=resolved_config.chunk_size):
            if chunk:
                file_obj.write(chunk)


def delete_file(
    remote_path: str,
    device_id: str,
    *,
    config: ClientConfig | None = None,
) -> DeleteFileResponse:
    response = _request(
        "DELETE",
        "/files",
        config=config,
        params={"path": remote_path, "device_id": device_id},
    )
    return DeleteFileResponse.model_validate(response.json())


def _request(
    method: str,
    endpoint: str,
    *,
    config: ClientConfig | None = None,
    **kwargs: object,
) -> Response:
    resolved_config = config or get_client_config()
    url = f"{resolved_config.server_url.rstrip('/')}{endpoint}"

    try:
        response = session.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
    except RequestException as exc:
        raise NetworkError(_build_error_message(endpoint, exc)) from exc

    return response


def _build_session() -> Session:
    client = requests.Session()
    client.trust_env = False
    return client


session = _build_session()


class MultipartUploadStream:
    def __init__(
        self,
        *,
        local_path: Path,
        remote_path: str,
        device_id: str,
        boundary: str,
        chunk_size: int,
    ) -> None:
        self.local_path = local_path
        self.remote_path = remote_path
        self.device_id = device_id
        self.boundary = boundary
        self.chunk_size = chunk_size
        self._sha256 = hashlib.sha256()

    def __iter__(self) -> Iterator[bytes]:
        yield _form_field(self.boundary, "path", self.remote_path)
        yield _form_field(self.boundary, "device_id", self.device_id)
        yield _file_field_header(self.boundary, self.local_path.name)

        for chunk in iter_file_chunks(self.local_path, chunk_size=self.chunk_size):
            self._sha256.update(chunk)
            yield chunk

        yield b"\r\n"
        yield f"--{self.boundary}--\r\n".encode()

    @property
    def digest(self) -> str:
        return self._sha256.hexdigest()


def _form_field(boundary: str, name: str, value: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode()


def _file_field_header(boundary: str, filename: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()


def _build_error_message(endpoint: str, exc: RequestException) -> str:
    response = exc.response
    if response is None:
        return f"Request to {endpoint} failed: {exc}"

    detail = _extract_error_detail(response)
    return f"Request to {endpoint} failed with status {response.status_code}: {detail}"


def _extract_error_detail(response: Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "Unknown error"

    if isinstance(payload, dict) and "detail" in payload:
        return str(payload["detail"])

    return str(payload)
