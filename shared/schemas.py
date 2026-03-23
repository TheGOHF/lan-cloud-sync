from datetime import datetime

from pydantic import BaseModel


class UploadFileResponse(BaseModel):
    path: str
    version: int
    hash: str


class FileMetadataResponse(BaseModel):
    path: str
    version: int
    hash: str
    updated_at: datetime
    deleted: bool


class DeleteFileResponse(BaseModel):
    path: str
    version: int
    deleted: bool
