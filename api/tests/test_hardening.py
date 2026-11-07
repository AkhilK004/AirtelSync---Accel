import pytest
from fastapi.testclient import TestClient

from app import hardening
from app.config import settings
from app.main import app
from app.repo.firestore import FirestoreRepo


# ------------------------------------------------------------------ rate limiter
def test_limiter_counts_and_window():
    hardening.reset_limits()
    path = "/checkout/otp"
    n, win = hardening.LIMITS[("POST", path)]
    for i in range(n):
        assert hardening.check_limit("1.1.1.1", "POST", path, now=100.0 + i * 0.1) is None
    wait = hardening.check_limit("1.1.1.1", "POST", path, now=101.5)
    assert wait is not None and 1 <= wait <= win
    assert hardening.check_limit("2.2.2.2", "POST", path, now=101.5) is None          # other client unaffected
    assert hardening.check_limit("1.1.1.1", "POST", path, now=100.0 + win + 5) is None  # window passed
    assert hardening.check_limit("1.1.1.1", "GET", "/health", now=1.0) is None          # unlimited route


def test_longest_prefix_wins():
    assert hardening.rule_for("POST", "/checkout/otp")[0] == "/checkout/otp"
    assert hardening.rule_for("POST", "/checkout")[0] == "/checkout"
    assert hardening.rule_for("POST", "/kyc/abc/documents")[0] == "/kyc/"
    assert hardening.rule_for("POST", "/advisor/sessions/x/messages")[0] == "/advisor/sessions/"
    assert hardening.rule_for("POST", "/advisor/sessions")[0] == "/advisor/sessions"


def test_middleware_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    hardening.reset_limits()
    c = TestClient(app)
    codes = [c.post("/checkout/otp", json={"phone": "9876543210"}).status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]
    r = c.post("/checkout/otp", json={"phone": "9876543210"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED" and int(r.headers["Retry-After"]) >= 1
    hardening.reset_limits()


def test_forwarded_ip_is_the_client_key(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    hardening.reset_limits()
    c = TestClient(app)
    for _ in range(10):
        c.post("/checkout/otp", json={"phone": "9876543210"}, headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"})
    assert c.post("/checkout/otp", json={"phone": "9876543210"}, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 429
    assert c.post("/checkout/otp", json={"phone": "9876543210"}, headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 200
    hardening.reset_limits()


# ------------------------------------------------------------------ headers + secrets
def test_security_headers_and_no_store():
    r = TestClient(app).get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY" and r.headers["cache-control"] == "no-store"
    assert r.json()["build"]


def test_prod_refuses_default_secrets(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        hardening.assert_prod_secrets()
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "s3cret-token")
    with pytest.raises(RuntimeError, match="BACKOFFICE_PASSWORD"):
        hardening.assert_prod_secrets()
    monkeypatch.setattr(settings, "BACKOFFICE_PASSWORD", "another-secret")
    hardening.assert_prod_secrets()
    monkeypatch.setattr(settings, "APP_ENV", "local")


# ------------------------------------------------------------------ FirestoreRepo against an in-memory fake client
class AlreadyExists(Exception):
    pass


class Snap:
    def __init__(self, store, key):
        self._s, self._k = store, key
        self.exists = key in store
        self.reference = self

    def to_dict(self):
        return dict(self._s[self._k])

    def delete(self):
        self._s.pop(self._k, None)


class Doc:
    def __init__(self, store, key):
        self.s, self.k = store, key

    def set(self, d):
        self.s[self.k] = dict(d)

    def get(self):
        return Snap(self.s, self.k)

    def create(self, d):
        if self.k in self.s:
            raise AlreadyExists()
        self.s[self.k] = dict(d)


class Col:
    def __init__(self, store):
        self.s = store

    def document(self, k):
        return Doc(self.s, k)

    def stream(self):
        return [Snap(self.s, k) for k in list(self.s)]


class FakeDb:
    def __init__(self):
        self.cols = {}

    def collection(self, name):
        return Col(self.cols.setdefault(name, {}))


def test_firestore_repo_contract():
    r = FirestoreRepo(FakeDb())
    r.put("orders", "a", {"x": 1})
    assert r.get("orders", "a") == {"x": 1} and r.get("orders", "zz") is None and r.list("orders") == [{"x": 1}]
    r.append("consents", "c1", {"k": "grant"})
    with pytest.raises(ValueError, match="append-only"):
        r.append("consents", "c1", {"k": "again"})
    r.clear()
    assert r.list("orders") == [] and r.list("consents") == []


def test_repo_switch_by_env(monkeypatch):
    from app import repo
    repo.get_repo.cache_clear()
    monkeypatch.setattr(settings, "STORAGE", "memory")
    assert type(repo.get_repo()).__name__ == "MemoryRepo"
    repo.get_repo.cache_clear()
    monkeypatch.setattr(settings, "STORAGE", "memory")
    repo.get_repo.cache_clear()
