"""Freeze source bytes once; publish rebuildable copies without business writes."""

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.archives.domain.paths import RULES, relative_path


def encoded(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(content):
    return hashlib.sha256(content).hexdigest()


@dataclass
class ArchiveWork:
    archives: object
    providers: dict
    journal: object


class Archives:
    def __init__(self, transaction, snapshot, store, copies, zipper):
        self.transaction, self.snapshot = transaction, snapshot
        self.store, self.copies, self.zipper = store, copies, zipper

    def settings(self, actor):
        with self.snapshot() as work:
            return {
                **work.archives.settings(actor),
                "root_configured": self.copies.root is not None,
            }

    def save_settings(self, actor, key, expected, rule):
        actor.require_write()
        self.rule(rule)
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "archive.settings", key, {"expected_version": expected, "rule": rule}
            )
            if prior is not None:
                return prior
            if work.archives.settings(actor)["version"] != expected:
                raise BusinessError("VERSION_CONFLICT", 409)
            work.archives.save_settings(actor, expected, rule)
            result = {
                **work.archives.settings(actor),
                "root_configured": self.copies.root is not None,
            }
            work.journal.audit(actor, "archive.settings", actor.organization_id)
            work.journal.finish(actor, "archive.settings", key, result)
            return result

    @staticmethod
    def rule(rule):
        if rule not in RULES:
            raise BusinessError("ARCHIVE_RULE_INVALID")

    @staticmethod
    def provider(work, key):
        try:
            kind, identifier = key.split(":", 1)
            UUID(identifier)
            return work.providers[kind]
        except ValueError, KeyError, AttributeError:
            raise BusinessError("ARCHIVE_SOURCE_INVALID") from None

    def catalog(self, actor, kind, cursor=None, limit=50):
        with self.snapshot() as work:
            if kind not in work.providers:
                raise BusinessError("ARCHIVE_SOURCE_INVALID")
            return work.providers[kind].catalog(actor, cursor, limit)

    def capture(self, work, actor, rule, selections):
        self.rule(rule)
        if not 1 <= len(selections) <= 50 or len({i["key"] for i in selections}) != len(selections):
            raise BusinessError("ARCHIVE_SELECTION_INVALID")
        items, files = [], {}
        total = 0
        for selection in sorted(selections, key=lambda i: i["key"]):
            item, content = self.provider(work, selection["key"]).capture(actor, selection["key"])
            if not item["available"]:
                raise BusinessError("ARCHIVE_SOURCE_UNAVAILABLE", 409)
            if item["token"] != selection["token"]:
                raise BusinessError("ARCHIVE_PREVIEW_STALE", 409)
            path = relative_path(rule, item)
            total += len(content)
            if total > 50 * 1024 * 1024:
                raise BusinessError("ARCHIVE_LIMIT_EXCEEDED", 413)
            if path in files:
                raise BusinessError("ARCHIVE_PATH_INVALID")
            files[path] = content
            items.append(
                {**item, "path": path, "sha256": digest(content), "byte_size": len(content)}
            )
        token = digest(encoded({"rule": rule, "items": items}))
        return {"items": items, "total_bytes": total, "preview_token": token}, files

    def preview(self, actor, rule, selections):
        with self.snapshot() as work:
            result, _ = self.capture(work, actor, rule, selections)
            return result

    def create(self, actor, key, rule, selections, preview_token):
        actor.require_write()
        if self.copies.root is None:
            raise BusinessError("ARCHIVE_NOT_CONFIGURED", 503)
        payload = {"rule": rule, "selections": selections, "preview_token": preview_token}
        # Snapshot conflicts repeat the entire command with the same idempotency key.
        for attempt in range(3):
            try:
                identifier = self._create(actor, key, payload)
                break
            except BusinessError as error:
                if error.code != "ARCHIVE_RETRY" or attempt == 2:
                    raise
        return self.detail(actor, identifier)

    def _create(self, actor, key, payload):
        with self.snapshot() as work:
            prior = work.journal.claim(actor, "archive.create", key, payload)
            if prior is not None:
                return prior["id"]
            preview, files = self.capture(work, actor, payload["rule"], payload["selections"])
            if preview["preview_token"] != payload["preview_token"]:
                raise BusinessError("ARCHIVE_PREVIEW_STALE", 409)
            fingerprint = preview["preview_token"]
            identifier = work.archives.find(actor, fingerprint)
            if identifier is None:
                identifier = uuid7()
                manifest = {
                    "type": "work-archive-v1",
                    "id": str(identifier),
                    "notice": "工作文件 · 生成时快照；不代表实时状态或正式结算。",
                    "created_at": datetime.now(UTC).isoformat(),
                    "rule": payload["rule"],
                    "items": preview["items"],
                    "total_bytes": preview["total_bytes"],
                }
                envelope = {
                    "type": "archive-input-v1",
                    "files": {
                        path: base64.b64encode(content).decode("ascii")
                        for path, content in files.items()
                    },
                }
                input_hash = self.store.put(encoded(envelope))
                work.archives.create(
                    actor, identifier, fingerprint, payload["rule"], input_hash, manifest
                )
                identifier = work.archives.find(actor, fingerprint)
                if identifier is None:
                    raise BusinessError("ARCHIVE_RETRY", 409)
                work.journal.audit(actor, "archive.create", identifier)
            work.journal.finish(actor, "archive.create", key, {"id": str(identifier)})
            return str(identifier)

    def inputs(self, record):
        try:
            envelope = json.loads(self.store.read(record["input_hash"]))
            if envelope["type"] != "archive-input-v1":
                raise ValueError()
            files = {
                path: base64.b64decode(content, validate=True)
                for path, content in envelope["files"].items()
            }
            expected = record["manifest"]["items"]
            if set(files) != {i["path"] for i in expected} or any(
                digest(files[i["path"]]) != i["sha256"] or len(files[i["path"]]) != i["byte_size"]
                for i in expected
            ):
                raise ValueError()
            return files
        except KeyError, ValueError, TypeError:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None

    def present(self, work, actor, record, inspect_local=False):
        current = True
        for item in record["manifest"]["items"]:
            try:
                live = self.provider(work, item["key"]).describe(actor, item["key"])
                current = current and live["token"] == item["token"] and live["current"]
            except BusinessError as error:
                if error.status != 404:
                    raise
                current = False
        result = {
            k: record[k] for k in ("id", "rule", "status", "file_hash", "error_code", "created_at")
        }
        result.update(
            current=current,
            items=record["manifest"]["items"],
            total_bytes=record["manifest"]["total_bytes"],
            local_available=None,
            local_error=None,
            relative_directory=f"{actor.organization_id}/{record['id']}",
        )
        if inspect_local:
            try:
                result["local_available"] = self.copies.available(
                    str(actor.organization_id),
                    record["id"],
                    self.inputs(record),
                    record["manifest"],
                )
            except BusinessError as error:
                result.update(local_available=False, local_error=error.code)
        return result

    def detail(self, actor, identifier):
        with self.snapshot() as work:
            return self.present(work, actor, work.archives.get(actor, identifier), True)

    def listing(self, actor, cursor=None, limit=25):
        with self.snapshot() as work:
            page = work.archives.listing(actor, cursor, limit)
            return {**page, "items": [self.present(work, actor, i) for i in page["items"]]}

    def generate(self, actor, identifier):
        actor.require_write()
        with self.snapshot() as work:
            record = work.archives.get(actor, identifier)
        error_code, object_hash, file_hash = None, None, None
        try:
            files = self.inputs(record)
            content = self.zipper(files, record["manifest"])
            file_hash = digest(content)
            object_hash = self.store.put(
                encoded(
                    {
                        "type": "archive-zip-v1",
                        "sha256": file_hash,
                        "content": base64.b64encode(content).decode("ascii"),
                    }
                )
            )
            if record["status"] == "ready" and (
                object_hash != record["object_hash"] or file_hash != record["file_hash"]
            ):
                raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
            self.copies.publish(
                str(actor.organization_id), str(identifier), files, record["manifest"]
            )
        except BusinessError as error:
            error_code = error.code
        except OSError:
            error_code = "ARCHIVE_WRITE_FAILED"
        with self.transaction() as work:
            live = work.archives.get(actor, identifier, lock=True)
            if live["status"] != "ready":
                work.archives.finish(
                    actor,
                    identifier,
                    None if error_code else object_hash,
                    None if error_code else file_hash,
                    error_code,
                )
                work.journal.audit(
                    actor, "archive.failed" if error_code else "archive.ready", identifier
                )
        if error_code and record["status"] == "ready":
            raise BusinessError(error_code, 409)
        return self.detail(actor, identifier)

    def download(self, actor, identifier, historical=False):
        with self.snapshot() as work:
            record = work.archives.get(actor, identifier)
            current = historical or self.present(work, actor, record)["current"]
        if record["status"] != "ready":
            raise BusinessError("ARCHIVE_NOT_READY", 409)
        if not current:
            raise BusinessError("ARCHIVE_STALE", 409)
        try:
            envelope = json.loads(self.store.read(record["object_hash"]))
            content = base64.b64decode(envelope["content"], validate=True)
            if envelope["type"] != "archive-zip-v1" or digest(content) != record["file_hash"]:
                raise ValueError()
        except KeyError, ValueError, TypeError:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None
        return content
