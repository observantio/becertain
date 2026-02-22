import asyncio
import pytest

from datasources.retry import retry


@pytest.mark.asyncio
async def test_retry_async_success_after_failure():
    calls = []

    @retry(attempts=3, delay=0.01, backoff=1, exceptions=(ValueError,))
    async def flaky(x):
        calls.append(x)
        if len(calls) < 2:
            raise ValueError("temporary")
        return x * 2

    result = await flaky(5)
    assert result == 10
    assert len(calls) == 2


def test_retry_sync_success_after_failure():
    calls = []

    @retry(attempts=4, delay=0.01, backoff=1, exceptions=(ValueError,))
    def flaky(x):
        calls.append(x)
        if len(calls) < 3:
            raise ValueError("oops")
        return x + 1

    result = flaky(7)
    assert result == 8
    assert len(calls) == 3


def test_retry_exhausted():
    @retry(attempts=2, delay=0.01, backoff=1, exceptions=(ValueError,))
    def always_fail():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        always_fail()
