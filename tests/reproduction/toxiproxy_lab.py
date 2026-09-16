"""Ephemeral real Toxiproxy container used by adapter integration tests."""

import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

TOXIPROXY_IMAGE = "ghcr.io/shopify/toxiproxy:2.12.0"


@dataclass(frozen=True)
class ToxiproxyLab:
    api_url: str
    proxy_url: str
    proxy_port: int
    container_name: str


def _available_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


@pytest.fixture
def toxiproxy_lab() -> Iterator[ToxiproxyLab]:
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable; real Toxiproxy integration was not run")
    info = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    if info.returncode != 0:
        pytest.skip("Docker daemon is unavailable; real Toxiproxy integration was not run")

    admin_port = _available_port()
    proxy_port = _available_port()
    name = f"ops-agent-toxiproxy-{uuid.uuid4().hex[:10]}"
    command = [
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        name,
        "--add-host",
        "host.docker.internal:host-gateway",
        "--publish",
        f"127.0.0.1:{admin_port}:8474",
        "--publish",
        f"127.0.0.1:{proxy_port}:{proxy_port}",
        TOXIPROXY_IMAGE,
    ]
    started = subprocess.run(command, capture_output=True, check=False, text=True, timeout=90)
    if started.returncode != 0:
        pytest.fail(f"could not start real Toxiproxy container: {started.stderr.strip()}")

    api_url = f"http://127.0.0.1:{admin_port}"
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                response = httpx.get(f"{api_url}/version", timeout=0.5)
                if response.is_success:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                pytest.fail("real Toxiproxy container did not become ready")
            time.sleep(0.1)
        yield ToxiproxyLab(
            api_url=api_url,
            proxy_url=f"http://127.0.0.1:{proxy_port}/",
            proxy_port=proxy_port,
            container_name=name,
        )
    finally:
        subprocess.run(
            ["docker", "rm", "--force", name],
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
