import hashlib

from store import keys


def test_slug_consistency():
    v = "hello"
    s1 = keys._slug(v)
    s2 = hashlib.md5(v.encode()).hexdigest()[:12]
    assert s1 == s2


def test_keys_format():
    tid = "tenant"
    assert keys.baseline(tid, "m") == f"bc:{tid}:baseline:{keys._slug('m')}"
    assert keys.weights(tid) == f"bc:{tid}:weights"
    assert keys.granger(tid, "svc").startswith(f"bc:{tid}:granger:")
    assert keys.events(tid) == f"bc:{tid}:events"
