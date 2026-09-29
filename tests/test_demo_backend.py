from __future__ import annotations

import asyncio
import time

import pytest

from openshell_ui.core.backends.base import (
    BackendError,
    CreateRequest,
    ExecRequest,
    phase_label,
)
from openshell_ui.core.backends.demo import DemoBackend


def request_for(name: str, workspace: str = "default") -> CreateRequest:
    return CreateRequest(name=name, workspace=workspace)


def test_health_reports_serving() -> None:
    body = asyncio.run(DemoBackend().health())
    assert body["status"] == "serving"
    assert body["backend"] == "demo"


def test_create_assigns_incrementing_ids() -> None:
    backend = DemoBackend()

    async def scenario() -> tuple[str, str]:
        first = await backend.create(request_for("a"))
        second = await backend.create(request_for("b"))
        return first.id, second.id

    first_id, second_id = asyncio.run(scenario())
    assert first_id == "demo-0001"
    assert second_id == "demo-0002"


def test_create_rejects_duplicate() -> None:
    backend = DemoBackend()

    async def scenario() -> None:
        await backend.create(request_for("a"))
        with pytest.raises(BackendError) as excinfo:
            await backend.create(request_for("a"))
        assert excinfo.value.status_code == 409

    asyncio.run(scenario())


def test_phase_transitions_to_ready() -> None:
    backend = DemoBackend()

    async def scenario() -> tuple[str, str]:
        view = await backend.create(request_for("a"))
        assert view.phase == "provisioning"
        await asyncio.sleep(0.9)
        return view.phase, (await backend.get("a", workspace="default")).phase

    before, after = asyncio.run(scenario())
    assert before == "provisioning"
    assert after == "ready"


def test_delete_removes_state() -> None:
    backend = DemoBackend()

    async def scenario() -> None:
        await backend.create(request_for("a"))
        await backend.delete("a", workspace="default")
        with pytest.raises(BackendError) as excinfo:
            await backend.get("a", workspace="default")
        assert excinfo.value.status_code == 404
        with pytest.raises(BackendError):
            await backend.delete("a", workspace="default")

    asyncio.run(scenario())


def test_exec_emits_stdout_then_exit() -> None:
    backend = DemoBackend(latency=0)

    async def scenario() -> list:
        await backend.create(request_for("a"))
        return [
            event
            async for event in backend.exec_stream(
                "a", ExecRequest(command=["echo", "hello"]), workspace="default"
            )
        ]

    events = asyncio.run(scenario())
    assert [event.type for event in events] == ["stdout", "stdout", "exit"]
    assert events[0].data == "$ echo hello\n"
    assert events[1].data == "hello\n"
    assert events[-1].exit_code == 0


def test_exec_unknown_sandbox_raises_404() -> None:
    backend = DemoBackend()

    async def scenario() -> None:
        with pytest.raises(BackendError) as excinfo:
            async for _ in backend.exec_stream(
                "ghost", ExecRequest(command=["ls"]), workspace="default"
            ):
                pass
        assert excinfo.value.status_code == 404

    asyncio.run(scenario())


def test_exec_script_covers_known_commands() -> None:
    backend = DemoBackend(latency=0)

    async def scenario() -> dict[str, str]:
        await backend.create(request_for("a"))
        out: dict[str, str] = {}
        for command in (["ls"], ["pwd"], ["whoami"], ["uname"], ["node"], ["frobnicate"]):
            events = [
                event
                async for event in backend.exec_stream(
                    "a", ExecRequest(command=command), workspace="default"
                )
            ]
            out[command[0]] = "".join(event.data for event in events)
        return out

    out = asyncio.run(scenario())
    assert "pyproject.toml" in out["ls"]
    assert "/workspace" in out["pwd"]
    assert "sandbox" in out["whoami"]
    assert "no real sandbox" in out["node"]
    assert "frobnicate" in out["frobnicate"]


def test_aclose_is_a_noop() -> None:
    asyncio.run(DemoBackend().aclose())


def test_provisioning_window_is_short() -> None:
    backend = DemoBackend()

    async def scenario() -> bool:
        await backend.create(request_for("a"))
        await asyncio.sleep(0.2)
        view = await backend.get("a", workspace="default")
        return view.phase == "provisioning"

    assert asyncio.run(scenario()) is True


def test_phase_label_maps_known_codes() -> None:
    assert phase_label(1) == "provisioning"
    assert phase_label(2) == "ready"
    assert phase_label(3) == "error"
    assert phase_label(999) == "unknown"


def test_demo_backend_keeps_workspaces_isolated() -> None:
    backend = DemoBackend()

    async def scenario() -> tuple[int, int]:
        await backend.create(request_for("same", workspace="a"))
        await backend.create(request_for("same", workspace="b"))
        return len(await backend.list(workspace="a")), len(await backend.list(workspace="b"))

    assert asyncio.run(scenario()) == (1, 1)


def test_list_without_workspace_returns_everything() -> None:
    backend = DemoBackend()

    async def scenario() -> int:
        await backend.create(request_for("a", workspace="x"))
        await backend.create(request_for("b", workspace="y"))
        return len(await backend.list())

    assert asyncio.run(scenario()) == 2


def test_create_latency_is_zero_in_tests() -> None:
    backend = DemoBackend(latency=0)
    start = time.monotonic()
    asyncio.run(backend.create(request_for("a")))
    assert time.monotonic() - start < 0.5
