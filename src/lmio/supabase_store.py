"""Durable Supabase persistence for the protected LMIO runtime.

The browser never receives the service-role key. All tables use the ``lmio_``
prefix and deny direct authenticated/anonymous access through RLS.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

RECORD_KINDS = {
    "universe_runs",
    "screen_runs",
    "valuation_runs",
    "reports",
    "signal_outcomes",
    "system_events",
    "research_packs",
    "conditional_plans",
    "provider_health",
    "provider_snapshots",
    "candidate_transitions",
    "trade_plan_transitions",
    "ownership_events",
    "signals",
    "user_feedback",
    "strategy_performance",
    "watchlists",
    "watchlist_members",
    "top3_evaluations",
    "pipeline_runs",
    "pipeline_stages",
    "news_price_confirmations",
}

LATEST_KINDS = {"universe_runs", "screen_runs", "reports"}

COUNT_KINDS = (
    "universe_runs",
    "screen_runs",
    "valuation_runs",
    "news_events",
    "reports",
    "signal_outcomes",
    "telegram_deliveries",
    "system_events",
    "research_packs",
    "conditional_plans",
    "provider_health",
    "symbols",
    "provider_snapshots",
    "candidate_transitions",
    "trade_plan_transitions",
    "ownership_events",
    "signals",
    "user_feedback",
    "strategy_performance",
    "watchlists",
    "watchlist_members",
    "top3_evaluations",
    "pipeline_runs",
    "pipeline_stages",
    "news_price_confirmations",
)


class SupabaseRuntimeStore:
    """Small PostgREST adapter over an isolated LMIO table set."""

    def __init__(
        self,
        url: str,
        service_role_key: str,
        *,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = self._client.request(
            method,
            f"{self.base_url}/{path.lstrip('/')}",
            params=params,
            json=json,
            headers=headers,
        )
        response.raise_for_status()
        return response

    def migrate(self) -> None:
        """Verify the migration exists without attempting DDL through PostgREST."""

        self._request("GET", "lmio_records", params={"select": "id", "limit": "1"})

    def connectivity_check(self) -> dict[str, Any]:
        self._request("GET", "lmio_schema_versions", params={"select": "version", "limit": "1"})
        return {"status": "ok", "backend": "supabase"}

    def schema_check(self) -> dict[str, Any]:
        versions = self.schema_versions()
        return {
            "status": "ok" if versions and max(versions) >= 10 else "failed",
            "schema_versions": versions,
            "required_version": 10,
        }

    def rls_check(self) -> dict[str, Any]:
        response = self._request("POST", "rpc/lmio_rls_check", json={})
        return dict(response.json())

    def record_count_check(self) -> dict[str, Any]:
        return {"status": "ok", "counts": self.counts()}

    def referential_integrity_check(self) -> dict[str, Any]:
        return {
            "status": "not_applicable",
            "reason": (
                "The current generic LMIO record store has no declared cross-table foreign keys."
            ),
        }

    def schema_versions(self) -> list[int]:
        response = self._request(
            "GET",
            "lmio_schema_versions",
            params={"select": "version", "order": "version.asc"},
        )
        return [int(item["version"]) for item in response.json()]

    def backup_export(self, destination: str | Path) -> dict[str, Any]:
        """Export every LMIO physical table to a hashed, local JSON recovery set."""

        target = Path(destination)
        if target.exists():
            raise FileExistsError(target)
        target.mkdir(parents=True)
        tables = (
            "lmio_schema_versions",
            "lmio_records",
            "lmio_ingestion_dedup",
            "lmio_news_events",
            "lmio_symbols",
            "lmio_telegram_deliveries",
            "lmio_synthetic_records",
        )
        files: dict[str, dict[str, Any]] = {}
        for table in tables:
            rows = self._request(
                "GET",
                table,
                params={"select": "*", "order": "created_at.asc"},
            ).json()
            content = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2, default=str)
            output = target / f"{table}.json"
            output.write_text(content)
            files[table] = {
                "file": output.name,
                "rows": len(rows),
                "sha256": sha256(output.read_bytes()).hexdigest(),
            }
        manifest = {
            "exported_at": datetime.now(UTC).isoformat(),
            "schema_versions": self.schema_versions(),
            "files": files,
            "limitations": [
                "This is a logical export, not point-in-time recovery.",
                "Provider-managed disaster recovery depends on the active Supabase plan.",
            ],
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        )
        return manifest

    @staticmethod
    def restore_rehearsal(export_directory: str | Path, target: str | Path) -> dict[str, Any]:
        """Load an export into an isolated SQLite evidence store and compare counts/hashes."""

        source = Path(export_directory)
        manifest = json.loads((source / "manifest.json").read_text())
        database = Path(target)
        if database.exists():
            raise FileExistsError(database)
        connection = sqlite3.connect(database)
        restored: dict[str, int] = {}
        try:
            connection.execute(
                "CREATE TABLE restored_records (source_table TEXT, row_index INTEGER, payload TEXT)"
            )
            for table, metadata in manifest["files"].items():
                path = source / metadata["file"]
                if sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
                    raise RuntimeError(f"Export hash mismatch for {table}")
                rows = json.loads(path.read_text())
                connection.executemany(
                    "INSERT INTO restored_records(source_table, row_index, payload) "
                    "VALUES (?, ?, ?)",
                    [
                        (table, index, json.dumps(row, sort_keys=True, default=str))
                        for index, row in enumerate(rows)
                    ],
                )
                restored[table] = len(rows)
            connection.commit()
        finally:
            connection.close()
        expected = {table: int(item["rows"]) for table, item in manifest["files"].items()}
        return {
            "status": "passed" if restored == expected else "failed",
            "expected_counts": expected,
            "restored_counts": restored,
            "target": str(database),
        }

    @staticmethod
    def _record_payload(kind: str, columns: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "kind": kind,
            "symbol": columns.get("symbol"),
            "provider": columns.get("provider"),
            "state": columns.get("state") or columns.get("new_state"),
            "payload": columns.get("payload", {}),
            "input_payload": columns.get("input_payload"),
            "result_payload": columns.get("result_payload"),
            "metadata": {
                key: value
                for key, value in columns.items()
                if key not in {"payload", "input_payload", "result_payload"}
            },
        }
        return payload

    def append_json(self, table: str, columns: dict[str, Any]) -> int:
        if table == "synthetic_records":
            response = self._request(
                "POST",
                "lmio_synthetic_records",
                json={
                    "record_type": columns["record_type"],
                    "provenance": str(columns["provenance"]),
                    "payload": columns.get("payload", {}),
                },
                headers={"Prefer": "return=representation"},
            )
            return int(response.json()[0]["id"])
        if table not in RECORD_KINDS:
            raise ValueError(f"unsupported append table: {table}")
        response = self._request(
            "POST",
            "lmio_records",
            json=self._record_payload(table, columns),
            headers={"Prefer": "return=representation"},
        )
        rows = response.json()
        return int(rows[0]["id"])

    @staticmethod
    def _expand_record(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata") or {}
        result = {
            "id": item["id"],
            **metadata,
            "payload": item.get("payload") or {},
            "created_at": item["created_at"],
        }
        if item.get("symbol") is not None:
            result["symbol"] = item["symbol"]
        if item.get("provider") is not None:
            result["provider"] = item["provider"]
        if item.get("state") is not None:
            result["state"] = item["state"]
        if item.get("input_payload") is not None:
            result["input_payload"] = item["input_payload"]
        if item.get("result_payload") is not None:
            result["result_payload"] = item["result_payload"]
        return result

    def latest_json(self, table: str) -> dict[str, Any] | list[Any] | None:
        if table not in LATEST_KINDS:
            raise ValueError(f"unsupported latest table: {table}")
        response = self._request(
            "GET",
            "lmio_records",
            params={
                "select": "payload",
                "kind": f"eq.{table}",
                "order": "id.desc",
                "limit": "1",
            },
        )
        rows = response.json()
        return rows[0]["payload"] if rows else None

    def latest_provider_health(self) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "lmio_records",
            params={
                "select": "provider,state,payload,created_at",
                "kind": "eq.provider_health",
                "order": "id.desc",
                "limit": "1",
            },
        )
        rows = response.json()
        return rows[0] if rows else None

    def history_json(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        if table == "synthetic_records":
            bounded_limit = max(1, min(limit, 200))
            response = self._request(
                "GET",
                "lmio_synthetic_records",
                params={
                    "select": "id,record_type,provenance,payload,created_at",
                    "order": "id.desc",
                    "limit": str(bounded_limit),
                },
            )
            return list(response.json())
        if table not in RECORD_KINDS:
            raise ValueError(f"unsupported history table: {table}")
        bounded_limit = max(1, min(limit, 200))
        response = self._request(
            "GET",
            "lmio_records",
            params={
                "select": (
                    "id,symbol,provider,state,payload,input_payload,"
                    "result_payload,metadata,created_at"
                ),
                "kind": f"eq.{table}",
                "order": "id.desc",
                "limit": str(bounded_limit),
            },
        )
        return [self._expand_record(item) for item in response.json()]

    def counts(self) -> dict[str, int]:
        response = self._request("POST", "rpc/lmio_runtime_counts", json={})
        payload = response.json()
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        return {kind: int(payload.get(kind, 0)) for kind in COUNT_KINDS}

    def put_news_event(self, fingerprint: str, payload: dict[str, Any]) -> bool:
        response = self._request(
            "POST",
            "lmio_news_events",
            json={"fingerprint": fingerprint, "payload": payload},
            headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
        )
        return bool(response.json())

    def put_ownership_event(
        self,
        fingerprint: str,
        *,
        symbol: str,
        event_type: str,
        source_url: str,
        payload: dict[str, Any],
    ) -> bool:
        response = self._request(
            "POST",
            "rpc/lmio_put_ownership_event",
            json={
                "p_fingerprint": fingerprint,
                "p_symbol": symbol,
                "p_event_type": event_type,
                "p_source_url": source_url,
                "p_payload": payload,
            },
        )
        return bool(response.json())

    def put_provider_snapshot(
        self,
        fingerprint: str,
        *,
        provider: str,
        symbol: str,
        company: str,
        observed_at: str,
        payload: dict[str, Any],
    ) -> bool:
        response = self._request(
            "POST",
            "rpc/lmio_put_provider_snapshot",
            json={
                "p_fingerprint": fingerprint,
                "p_provider": provider,
                "p_symbol": symbol,
                "p_company": company,
                "p_observed_at": observed_at,
                "p_payload": payload,
            },
        )
        return bool(response.json())

    def has_ingestion_fingerprint(self, fingerprint: str) -> bool:
        response = self._request(
            "GET",
            "lmio_ingestion_dedup",
            params={"select": "fingerprint", "fingerprint": f"eq.{fingerprint}", "limit": "1"},
        )
        return bool(response.json())

    def mark_ingestion_fingerprint(self, fingerprint: str, record_type: str) -> bool:
        response = self._request(
            "POST",
            "lmio_ingestion_dedup",
            json={"fingerprint": fingerprint, "record_type": record_type},
            headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
        )
        return bool(response.json())

    def news_payloads(self, limit: int = 500) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 2000))
        response = self._request(
            "GET",
            "lmio_news_events",
            params={
                "select": "payload",
                "order": "created_at.desc",
                "limit": str(bounded_limit),
            },
        )
        return [item["payload"] for item in response.json()]

    def news_event(self, fingerprint: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "lmio_news_events",
            params={
                "select": "payload",
                "fingerprint": f"eq.{fingerprint}",
                "limit": "1",
            },
        )
        rows = response.json()
        return rows[0]["payload"] if rows else None

    def telegram_delivery(self, key: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "lmio_telegram_deliveries",
            params={
                "select": "status,attempt_count",
                "dedupe_key": f"eq.{key}",
                "limit": "1",
            },
        )
        rows = response.json()
        return rows[0] if rows else None

    def claim_telegram_deliveries(
        self,
        *,
        claim_token: str,
        limit: int,
        max_attempts: int,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            "rpc/lmio_claim_telegram_deliveries",
            json={
                "p_claim_token": claim_token,
                "p_limit": max(1, min(limit, 50)),
                "p_max_attempts": max_attempts,
            },
        )
        return list(response.json())

    def sent_telegram_count_since(self, since: datetime) -> int:
        response = self._request(
            "GET",
            "lmio_telegram_deliveries",
            params={
                "select": "dedupe_key",
                "status": "eq.sent",
                "created_at": f"gte.{since.astimezone(UTC).isoformat()}",
            },
            headers={"Prefer": "count=exact"},
        )
        content_range = response.headers.get("content-range", "*/0")
        return int(content_range.rsplit("/", maxsplit=1)[-1])

    def upsert_telegram_delivery(
        self,
        *,
        key: str,
        status: str,
        payload: dict[str, Any],
        provider_message_id: str | None,
        attempt_increment: int,
    ) -> None:
        self._request(
            "POST",
            "rpc/lmio_upsert_telegram_delivery",
            json={
                "p_dedupe_key": key,
                "p_status": status,
                "p_payload": payload,
                "p_provider_message_id": provider_message_id,
                "p_attempt_increment": attempt_increment,
            },
        )

    def sent_telegram_count_last_hour(self) -> int:
        return self.sent_telegram_count_since(datetime.now(UTC) - timedelta(hours=1))
