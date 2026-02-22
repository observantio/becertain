import pytest

from store import weights as wstore


@pytest.mark.asyncio
async def test_weights_lifecycle():
    tid = "tenant123"
    assert await wstore.load(tid) is None
    data = {"metrics": 0.6, "logs": 0.4}
    await wstore.save(tid, data, update_count=5)
    stored = await wstore.load(tid)
    assert stored["weights"] == data
    assert stored["update_count"] == 5
    await wstore.delete(tid)
    assert await wstore.load(tid) is None


def test_weights_key_format():
    tid = "foo"
    k = wstore.weights(tid)
    assert "foo" in k
    assert k.startswith("bc:foo:weights")
