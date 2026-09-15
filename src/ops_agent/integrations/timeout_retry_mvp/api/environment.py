"""Isolated FastAPI + httpx + SQLite API environment for the first real MVP case."""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class CreateOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: str = Field(min_length=1)


class ScenarioObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_id: str
    trace_id: str
    request_ids: list[str]
    order_ids: list[int]
    retry_count: int
    page_events: list[str]


class TimeoutRetryEnvironment:
    """Own all test resources and inject delay only after the first DB commit."""

    BUSINESS_ID = "BIZ-MVP-001"
    TRACE_ID = "TRACE-MVP-001"
    CLIENT_TIMEOUT_SECONDS = 0.02
    FIRST_RESPONSE_DELAY_SECONDS = 0.08
    HTML = """<!doctype html>
<html lang="zh-CN"><body>
<form id="create-order"><button type="submit">创建订单</button></form>
<output id="status">idle</output>
</body></html>
"""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.database_path = output_dir / "orders.sqlite3"
        self.requests_path = output_dir / "requests.jsonl"
        self.logs_path = output_dir / "application.log"
        self.page_path = output_dir / "page-events.json"
        self.html_path = output_dir / "order-page.html"
        self._client: httpx.AsyncClient | None = None
        self._request_sequence = 0
        self.active = False

    async def setup(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.html_path.write_text(self.HTML, encoding="utf-8")
        self._initialize_database()
        self._clear_observation_files()
        app = self._create_app()
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://mvp-order.test",
        )
        self.active = True

    async def reset(self) -> None:
        if not self.active:
            raise RuntimeError("MVP environment is not active")
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("DELETE FROM orders")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'orders'")
            connection.commit()
        self._request_sequence = 0
        self._clear_observation_files()

    async def run_scenario(self) -> ScenarioObservation:
        if self._client is None or not self.active:
            raise RuntimeError("MVP environment is not active")
        await self._client.get("/")
        events = ["submit"]
        request_ids = ["HTTP-REQ-1", "HTTP-REQ-2"]
        first = asyncio.create_task(self._post_order(request_ids[0]))
        try:
            await asyncio.wait_for(first, timeout=self.CLIENT_TIMEOUT_SECONDS)
        except TimeoutError:
            events.extend(["timeout", "retry"])
        else:
            raise RuntimeError("first response did not exceed the configured client timeout")

        response = await self._post_order(request_ids[1])
        response.raise_for_status()
        events.append("success")
        order_ids = self.order_ids(self.BUSINESS_ID)
        page_payload = {"events": events, "retry_count": 1, "final_status": "created"}
        self.page_path.write_text(
            json.dumps(page_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return ScenarioObservation(
            business_id=self.BUSINESS_ID,
            trace_id=self.TRACE_ID,
            request_ids=request_ids,
            order_ids=order_ids,
            retry_count=1,
            page_events=events,
        )

    async def cleanup(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self.active = False

    def order_ids(self, business_id: str) -> list[int]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT id FROM orders WHERE business_id = ? ORDER BY id",
                (business_id,),
            ).fetchall()
        return [int(row[0]) for row in rows]

    def request_records(self) -> list[dict[str, JsonValue]]:
        return [
            cast(dict[str, JsonValue], json.loads(line))
            for line in self.requests_path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def _create_app(self) -> FastAPI:
        app = FastAPI(title="MVP Non-idempotent Order Backend")

        @app.get("/", response_class=HTMLResponse)
        async def order_page() -> str:
            return self.HTML

        @app.post("/orders")
        async def create_order(
            body: CreateOrderBody,
            x_request_id: str = Header(),
            x_trace_id: str = Header(),
        ) -> dict[str, object]:
            self._request_sequence += 1
            sequence = self._request_sequence
            with sqlite3.connect(self.database_path) as connection:
                cursor = connection.execute(
                    "INSERT INTO orders (business_id, request_id, trace_id) VALUES (?, ?, ?)",
                    (body.business_id, x_request_id, x_trace_id),
                )
                connection.commit()
                if cursor.lastrowid is None:
                    raise RuntimeError("SQLite did not return an order id")
                order_id = cursor.lastrowid
            delay = self.FIRST_RESPONSE_DELAY_SECONDS if sequence == 1 else 0.0
            record: dict[str, JsonValue] = {
                "sequence": sequence,
                "method": "POST",
                "path": "/orders",
                "business_id": body.business_id,
                "request_id": x_request_id,
                "trace_id": x_trace_id,
                "created": True,
                "order_id": order_id,
                "client_timeout_ms": int(self.CLIENT_TIMEOUT_SECONDS * 1000),
                "response_delay_ms": int(delay * 1000),
            }
            self._append_json(self.requests_path, record)
            self._append_json(
                self.logs_path,
                cast(
                    dict[str, JsonValue],
                    {
                        "level": "INFO",
                        "event": "order_created",
                        "request_id": x_request_id,
                        "trace_id": x_trace_id,
                        "business_id": body.business_id,
                        "order_id": order_id,
                    },
                ),
            )
            if delay:
                await asyncio.sleep(delay)
            return {"order_id": order_id, "business_id": body.business_id}

        return app

    async def _post_order(self, request_id: str) -> httpx.Response:
        assert self._client is not None
        return await self._client.post(
            "/orders",
            json={"business_id": self.BUSINESS_ID},
            headers={"x-request-id": request_id, "x-trace-id": self.TRACE_ID},
        )

    def _initialize_database(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL
                )
                """
            )
            connection.execute("DELETE FROM orders")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'orders'")
            connection.commit()

    def _clear_observation_files(self) -> None:
        self.requests_path.write_text("", encoding="utf-8")
        self.logs_path.write_text("", encoding="utf-8")
        self.page_path.write_text("{}\n", encoding="utf-8")

    @staticmethod
    def _append_json(path: Path, value: dict[str, JsonValue]) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")
