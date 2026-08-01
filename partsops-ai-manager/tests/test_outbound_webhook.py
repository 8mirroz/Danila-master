import json
from models import OutboundMessage
from app.automation.jobs import outbound_dispatch_job

def test_webhook_requires_https_and_configured_secret(monkeypatch):
    message = OutboundMessage(tenant_id="tenant-a", channel="webhook", recipient="http://example.test/hook", body_text="event", idempotency_key="webhook-1")
    success, error = outbound_dispatch_job._dispatch_webhook(message)
    assert not success and "HTTPS" in (error or "")
    message.recipient = "https://example.test/hook"
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_ALLOWED_HOSTS", "example.test")
    monkeypatch.delenv("PARTSOPS_OUTBOUND_WEBHOOK_SECRET", raising=False)
    success, error = outbound_dispatch_job._dispatch_webhook(message)
    assert not success and "secret" in (error or "")

def test_webhook_signs_canonical_envelope(monkeypatch):
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("PARTSOPS_OUTBOUND_WEBHOOK_ALLOWED_HOSTS", "example.test")
    message = OutboundMessage(id=7, tenant_id="tenant-a", request_id="REQ-1", channel="webhook", recipient="https://example.test/hook", subject="ready", body_text="event", payload_json=json.dumps({"status": "ready"}), idempotency_key="webhook-2")
    class Response: status_code = 202
    captured = {}
    monkeypatch.setattr("httpx.post", lambda url, **kwargs: captured.update(url=url, **kwargs) or Response())
    success, error = outbound_dispatch_job._dispatch_webhook(message)
    assert success and error is None
    assert captured["headers"]["X-PartsOps-Event-ID"] == "webhook-2"
    assert captured["headers"]["X-PartsOps-Signature"].startswith("sha256=")
