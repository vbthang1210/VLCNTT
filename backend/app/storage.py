from __future__ import annotations

import json
import secrets
import wave
from pathlib import Path
from threading import Lock

from werkzeug.datastructures import FileStorage

from .metadata import extension_for, extract_metadata, validate_mime


class AudioRepository:
    def __init__(self, storage_path: Path, metadata_path: Path, max_audio_size: int):
        self.storage_path = Path(storage_path)
        self.metadata_path = Path(metadata_path)
        self.max_audio_size = max_audio_size
        self._lock = Lock()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_records(self) -> dict[str, dict]:
        if not self.metadata_path.exists():
            return {}
        try:
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError("Metadata index is unreadable") from exc
        return data if isinstance(data, dict) else {}

    def _write_records(self, records: dict[str, dict]) -> None:
        temp = self.metadata_path.with_suffix(".tmp")
        temp.write_text(json.dumps(records, indent=2), encoding="utf-8")
        temp.replace(self.metadata_path)

    def list(self) -> list[dict]:
        with self._lock:
            return list(self._read_records().values())

    def get(self, audio_id: str) -> dict | None:
        with self._lock:
            return self._read_records().get(audio_id)

    def update_metadata(self, audio_id: str, updates: dict) -> dict | None:
        with self._lock:
            records = self._read_records()
            record = records.get(audio_id)
            if record is None:
                return None
            record.update(updates)
            self._write_records(records)
            return record

    def delete(self, audio_id: str) -> dict | None:
        with self._lock:
            records = self._read_records()
            record = records.get(audio_id)
            if record is None:
                return None
            filename = record.get("filename")
            if not isinstance(filename, str) or not filename:
                raise RuntimeError("Invalid storage filename")
            path = self.storage_path / filename
            if path.parent != self.storage_path:
                raise RuntimeError("Invalid storage path")
            path.unlink(missing_ok=True)
            records.pop(audio_id)
            self._write_records(records)
            return record

    def path_for(self, audio_id: str) -> Path:
        record = self.get(audio_id)
        if not record:
            raise FileNotFoundError(audio_id)
        path = self.storage_path / record["filename"]
        if path.parent != self.storage_path:
            raise RuntimeError("Invalid storage path")
        return path

    def save_upload(self, upload: FileStorage) -> dict:
        if not upload.filename:
            raise ValueError("Filename is required")
        audio_format = extension_for(upload.filename)
        validate_mime(upload.mimetype)
        source = upload.stream
        source.seek(0)
        payload = source.read(self.max_audio_size + 1)
        if len(payload) > self.max_audio_size:
            raise ValueError("Audio file exceeds the 20 MiB limit")
        if not payload:
            raise ValueError("Audio file is empty")

        audio_id = f"audio_{secrets.token_hex(4)}"
        filename = f"{audio_id}.{audio_format}"
        destination = self.storage_path / filename
        destination.write_bytes(payload)
        try:
            metadata = extract_metadata(destination, audio_format)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        record = {
            "id": audio_id,
            "audio_id": audio_id,
            "filename": filename,
            "original_filename": Path(upload.filename).name,
            "format": audio_format,
            "size": len(payload),
            "status": "READY",
            **metadata,
        }
        with self._lock:
            records = self._read_records()
            records[audio_id] = record
            self._write_records(records)
        return record

    def save_pcm_recording(
        self,
        recording_id: str,
        pcm_path: Path,
        sample_rate: int,
        channels: int,
        bits_per_sample: int,
        metadata: dict,
    ) -> dict:
        filename = f"{recording_id}.wav"
        destination = self.storage_path / filename
        if destination.exists():
            pcm_path.unlink(missing_ok=True)
            raise ValueError("Recording already exists")
        try:
            with wave.open(str(destination), "wb") as output:
                output.setnchannels(channels)
                output.setsampwidth(bits_per_sample // 8)
                output.setframerate(sample_rate)
                with Path(pcm_path).open("rb") as source:
                    while chunk := source.read(64 * 1024):
                        output.writeframesraw(chunk)
            record = {
                "id": recording_id,
                "audio_id": recording_id,
                "filename": filename,
                "original_filename": filename,
                "format": "wav",
                "status": "READY",
                "sample_rate": sample_rate,
                "channels": channels,
                "bits_per_sample": bits_per_sample,
                **metadata,
                "size": destination.stat().st_size,
            }
            with self._lock:
                records = self._read_records()
                records[recording_id] = record
                self._write_records(records)
            return record
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            pcm_path.unlink(missing_ok=True)

    def delete_all_for_tests(self) -> None:
        with self._lock:
            for path in self.storage_path.glob("audio_*"):
                path.unlink(missing_ok=True)
            for path in (self.storage_path / ".recordings").glob(".*.pcm"):
                path.unlink(missing_ok=True)
            self._write_records({})
