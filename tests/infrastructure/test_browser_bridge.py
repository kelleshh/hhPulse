import asyncio

from fastapi.testclient import TestClient

from hhpulse.api.app import create_app
from hhpulse.bootstrap import Container
from hhpulse.config import Settings
from hhpulse.infrastructure.browser.bridge import BrowserBridge


async def test_companion_receives_one_command_and_only_matching_reply_completes_it():
    bridge = BrowserBridge()
    request = asyncio.create_task(
        bridge.request(url="https://hh.ru/search/resume?area=1", target="resume")
    )
    command = await bridge.next_command()
    assert command is not None
    assert bridge.connected
    assert await bridge.submit("wrong", {"status": "ok"}) is False
    assert not request.done()
    assert await bridge.submit(command["id"], {"status": "ok", "total": 1}) is True
    assert await request == {"status": "ok", "total": 1}
    assert await bridge.submit(command["id"], {"status": "ok"}) is False


def test_browser_bridge_requires_local_pairing_token():
    bridge = BrowserBridge()
    container = Container(
        settings=Settings(browser_token="secret"),
        clock=None,
        jobs=None,
        executions=None,
        browser_bridge=bridge,
    )
    with TestClient(create_app(container=container)) as client:
        assert client.get("/api/v1/browser/next").status_code == 403
        assert (
            client.post(
                "/api/v1/browser/result",
                headers={"X-HHPULSE-BROWSER-TOKEN": "wrong"},
                json={"command_id": "old", "result": {"status": "ok"}},
            ).status_code
            == 403
        )
