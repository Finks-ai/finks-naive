"""Finks Signals run id: `x-finks-run` is logged as `run_id` for the request, nothing else."""

import asyncio
import json

import pytest
from loguru import logger
from starlette.requests import Request

from app.main import bind_finks_run


@pytest.mark.parametrize(
    "header_value, expected",
    [
        ("run_01:qa.screener-7", "run_01:qa.screener-7"),
        (None, None),
        ("bad id\n", None),
        ("x" * 129, None),
    ],
)
def test_run_id_logged_only_when_valid(capsys, header_value, expected):
    headers = [] if header_value is None else [(b"x-finks-run", header_value.encode())]

    async def call_next(request):
        logger.error("probe")
        return "response"

    request = Request({"type": "http", "headers": headers})
    assert asyncio.run(bind_finks_run(request, call_next)) == "response"
    logger.error("after")

    probe, after = [json.loads(line) for line in capsys.readouterr().out.splitlines()[-2:]]
    assert probe["level"] == "ERROR" and probe["message"] == "probe"
    assert probe.get("run_id") == expected
    assert "run_id" not in after
