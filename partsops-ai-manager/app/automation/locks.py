"""
Locks — tenant-scoped named locks with TTL-backed expiry semantics.

Uses the AutomationLock table. If the DB row is missing, expired, or held
by a different owner_key, lock acquisition is denied.
"""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select
from models import AutomationLock


class LockAcquisitionError(Exception):
    pass


class AutomationLocks:
    def __init__(self, session: Session, default_ttl_seconds: int = 1800):
        self._session = session
        self._default_ttl = default_ttl_seconds

    def _build_owner_key(self, job_name: str, host: Optional[str] = None, pid: Optional[int] = None) -> str:
        parts = [job_name]
        if host:
            parts.append(host)
        if pid is not None:
            parts.append(str(pid))
        return "|".join(parts)

    def acquire_lock(
        self,
        tenant_id: str,
        lock_name: str,
        owner_key: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        blocking: bool = False,
        retry_count: int = 3,
        retry_sleep: float = 0.1,
    ) -> AutomationLock:
        """
        Acquire the named lock for tenant_id.

        Returns the AutomationLock record (active). Raises
        LockAcquisitionError if the lock is held by another owner.
        """
        if not owner_key:
            owner_key = self._build_owner_key(
                lock_name,
                host=getattr(threading.current_thread(), "name", None) or "host",
                pid=0,
            )
        ttl = ttl_seconds or self._default_ttl
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        for attempt in range(retry_count):
            existing = self._session.exec(
                select(AutomationLock)
                .where(AutomationLock.tenant_id == tenant_id)
                .where(AutomationLock.lock_name == lock_name)
                .where(AutomationLock.status == "active")
            ).first()

            if not existing:
                row = AutomationLock(
                    tenant_id=tenant_id,
                    lock_name=lock_name,
                    owner_key=owner_key,
                    expires_at=expires_at,
                    status="active",
                )
                self._session.add(row)
                self._session.commit()
                self._session.refresh(row)
                return row

            if existing.owner_key == owner_key:
                if not blocking or (existing.expires_at and existing.expires_at < datetime.utcnow()):
                    existing.status = "released"
                    existing.released_at = datetime.utcnow()
                self._session.add(existing)
                self._session.commit()
                return existing

            if existing.expires_at and existing.expires_at < datetime.utcnow():
                existing.status = "expired"
                existing.released_at = datetime.utcnow()
                self._session.add(existing)
                self._session.commit()
                continue

            if blocking:
                self._session.expunge(existing)
                time.sleep(retry_sleep)
                continue

            raise LockAcquisitionError(
                f"Lock acquisition failed: tenant={tenant_id} lock={lock_name} "
                f"held_by={existing.owner_key} expires_at={existing.expires_at}"
            )

        acquired = self.acquire_lock(
            tenant_id=tenant_id,
            lock_name=lock_name,
            owner_key=owner_key,
            ttl_seconds=ttl_seconds,
            blocking=False,
        )
        return acquired

    def release_lock(self, tenant_id: str, lock_name: str, owner_key: Optional[str] = None) -> None:
        lock = self._session.exec(
            select(AutomationLock)
            .where(AutomationLock.tenant_id == tenant_id)
            .where(AutomationLock.lock_name == lock_name)
            .where(AutomationLock.status == "active")
        ).first()
        if not lock:
            return
        if owner_key and lock.owner_key != owner_key:
            return
        lock.status = "released"
        lock.released_at = datetime.utcnow()
        self._session.add(lock)
        self._session.commit()


# Convenience wrapper (existing callers don't have to instantiate).
_global_session: Optional[Session] = None
_global_locks: Optional[AutomationLocks] = None


def set_locks_session(session: Session) -> AutomationLocks:
    global _global_session, _global_locks
    _global_session = session
    _global_locks = AutomationLocks(session)
    return _global_locks


def acquire_lock(*args, **kwargs):
    if _global_locks is None:
        raise RuntimeError("AutomationLocks session not set. Call set_locks_session() first.")
    return _global_locks.acquire_lock(*args, **kwargs)


def release_lock(*args, **kwargs):
    if _global_locks is None:
        return
    _global_locks.release_lock(*args, **kwargs)
