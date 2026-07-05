from datetime import datetime, timezone
from uuid import uuid4

class EventLogger:
    def log(self, source: str, severity: str, message: str, **payload):
        return {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "severity": severity,
            "message": message,
            "payload": payload,
        }
