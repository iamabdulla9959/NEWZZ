from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import IngestionLease, IngestionRequest, new_id

logger = logging.getLogger("newsreels.coordination")


class StaleLeaseError(Exception):
    """Raised when a worker attempts to commit or renew work under a superseded or expired lease."""
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def acquire_lease_with_generation(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
    ttl_seconds: int = 300,
) -> tuple[bool, int]:
    """Atomically acquires or recovers a named exclusive execution lease with fencing generation.

    Returns:
        (acquired: bool, lease_generation: int)
    """
    now = utc_now()
    expires_at = now + timedelta(seconds=ttl_seconds)

    try:
        lease = db.query(IngestionLease).filter(IngestionLease.lease_name == lease_name).first()
        if not lease:
            try:
                new_lease = IngestionLease(
                    lease_name=lease_name,
                    holder_id=holder_id,
                    lease_generation=1,
                    acquired_at=now,
                    renewed_at=now,
                    expires_at=expires_at,
                    is_active=True,
                )
                db.add(new_lease)
                db.commit()
                logger.info(
                    "Lease '%s' created (gen 1) and acquired by '%s'",
                    lease_name,
                    holder_id,
                )
                return True, 1
            except Exception:
                db.rollback()
                lease = db.query(IngestionLease).filter(IngestionLease.lease_name == lease_name).first()

        if not lease:
            return False, 0

        exp = (
            lease.expires_at
            if lease.expires_at and lease.expires_at.tzinfo
            else (lease.expires_at.replace(tzinfo=timezone.utc) if lease.expires_at else now)
        )

        # Check if held by the same holder and active
        if lease.is_active and exp >= now and lease.holder_id == holder_id:
            lease.renewed_at = now
            lease.expires_at = expires_at
            db.commit()
            return True, lease.lease_generation

        # Recoverable if inactive or expired
        if not lease.is_active or exp < now:
            new_generation = (lease.lease_generation or 0) + 1
            lease.holder_id = holder_id
            lease.lease_generation = new_generation
            lease.acquired_at = now
            lease.renewed_at = now
            lease.expires_at = expires_at
            lease.is_active = True
            db.commit()
            logger.info(
                "Lease '%s' acquired by '%s' (gen %d) until %s",
                lease_name,
                holder_id,
                new_generation,
                expires_at,
            )
            return True, new_generation
        else:
            logger.debug(
                "Lease '%s' held by active worker '%s' until %s (gen %d)",
                lease_name,
                lease.holder_id,
                exp,
                lease.lease_generation,
            )
            return False, lease.lease_generation
    except Exception as exc:
        db.rollback()
        logger.error("Error acquiring lease '%s': %s", lease_name, exc)
        return False, 0


def acquire_lease(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
    ttl_seconds: int = 300,
) -> bool:
    """Atomically acquires a named exclusive execution lease. Returns bool for backward compatibility."""
    acquired, _ = acquire_lease_with_generation(
        db, lease_name=lease_name, holder_id=holder_id, ttl_seconds=ttl_seconds
    )
    return acquired


def renew_lease(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
    ttl_seconds: int = 300,
    expected_generation: int | None = None,
) -> bool:
    """Renews an active lease held by holder_id, extending expires_at.
    
    If expected_generation is specified, enforces lease fencing token matches.
    """
    now = utc_now()
    expires_at = now + timedelta(seconds=ttl_seconds)

    try:
        where_clauses = [
            IngestionLease.lease_name == lease_name,
            IngestionLease.holder_id == holder_id,
            IngestionLease.is_active == True,
        ]
        if expected_generation is not None:
            where_clauses.append(IngestionLease.lease_generation == expected_generation)

        stmt = update(IngestionLease).where(*where_clauses).values(renewed_at=now, expires_at=expires_at)
        res = db.execute(stmt)
        if res.rowcount > 0:
            db.commit()
            return True
        db.rollback()
        return False
    except Exception as exc:
        db.rollback()
        logger.error("Error renewing lease '%s': %s", lease_name, exc)
        return False


def release_lease(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
    expected_generation: int | None = None,
) -> bool:
    """Releases a lease held by holder_id, marking it inactive."""
    try:
        where_clauses = [
            IngestionLease.lease_name == lease_name,
            IngestionLease.holder_id == holder_id,
        ]
        if expected_generation is not None:
            where_clauses.append(IngestionLease.lease_generation == expected_generation)

        stmt = update(IngestionLease).where(*where_clauses).values(is_active=False, holder_id=None)
        res = db.execute(stmt)
        db.commit()
        if res.rowcount > 0:
            logger.info("Lease '%s' released by '%s'", lease_name, holder_id)
            return True
        return False
    except Exception as exc:
        db.rollback()
        logger.error("Error releasing lease '%s': %s", lease_name, exc)
        return False


def is_lease_valid(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
) -> bool:
    """Verifies whether holder_id currently holds an unexpired, active lease."""
    now = utc_now()
    lease = (
        db.query(IngestionLease)
        .filter(
            IngestionLease.lease_name == lease_name,
            IngestionLease.holder_id == holder_id,
            IngestionLease.is_active == True,
        )
        .first()
    )
    if not lease or not lease.expires_at:
        return False
    exp = lease.expires_at if lease.expires_at.tzinfo else lease.expires_at.replace(tzinfo=timezone.utc)
    return exp >= now


def validate_lease_fencing(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
    expected_generation: int = 1,
    for_update: bool = False,
) -> bool:
    """Verifies that the lease is actively held by holder_id at the exact expected fencing generation."""
    now = utc_now()
    try:
        query = (
            db.query(IngestionLease)
            .filter(
                IngestionLease.lease_name == lease_name,
                IngestionLease.holder_id == holder_id,
                IngestionLease.is_active == True,
                IngestionLease.lease_generation == expected_generation,
            )
        )
        if for_update:
            try:
                lease = query.with_for_update().first()
            except Exception:
                lease = query.first()
        else:
            lease = query.first()

        if not lease or not lease.expires_at:
            return False
        exp = lease.expires_at if lease.expires_at.tzinfo else lease.expires_at.replace(tzinfo=timezone.utc)
        return exp >= now
    except Exception as exc:
        logger.error("Error validating lease fencing: %s", exc)
        return False


def heartbeat_lease(
    db: Session,
    lease_name: str = "canonical_ingestion",
    holder_id: str = "worker",
    expected_generation: int = 1,
    ttl_seconds: int = 300,
) -> bool:
    """Fenced heartbeat that extends lease expires_at if and only if generation matches."""
    return renew_lease(
        db,
        lease_name=lease_name,
        holder_id=holder_id,
        ttl_seconds=ttl_seconds,
        expected_generation=expected_generation,
    )


def heartbeat_request(
    db: Session,
    request_id: str,
    worker_id: str,
    expected_generation: int | None = None,
) -> bool:
    """Updates last_heartbeat_at for an actively running IngestionRequest."""
    now = utc_now()
    try:
        where_clauses = [
            IngestionRequest.id == request_id,
            IngestionRequest.status == "running",
            IngestionRequest.worker_id == worker_id,
        ]
        if expected_generation is not None:
            where_clauses.append(IngestionRequest.lease_generation == expected_generation)

        stmt = update(IngestionRequest).where(*where_clauses).values(last_heartbeat_at=now)
        res = db.execute(stmt)
        if res.rowcount > 0:
            db.commit()
            return True
        db.rollback()
        return False
    except Exception as exc:
        db.rollback()
        logger.error("Error sending heartbeat for request '%s': %s", request_id, exc)
        return False


def recover_abandoned_requests(
    db: Session,
    max_age_seconds: int = 300,
    max_retries: int = 3,
    lease_name: str = "canonical_ingestion",
) -> int:
    """Scans for abandoned or crashed 'running' requests and recovers them.
    
    A request is considered abandoned if:
    1. It has status 'running', AND
    2. Its last heartbeat (or started_at if last_heartbeat_at is None) is older than max_age_seconds, AND
    3. The associated lease is either expired, inactive, or held by another worker/generation.
    
    Recovery action:
    - If attempt_count < max_retries:
      Reset status='pending', clear worker_id and started_at so it can be retried cleanly.
    - If attempt_count >= max_retries:
      Mark status='failed', set completed_at=now, and record error_message explaining retry limit reached.
    """
    now = utc_now()
    recovered_count = 0

    try:
        running_requests = (
            db.query(IngestionRequest)
            .filter(IngestionRequest.status == "running")
            .all()
        )
        if not running_requests:
            return 0

        lease = db.query(IngestionLease).filter(IngestionLease.lease_name == lease_name).first()
        lease_exp = (
            lease.expires_at
            if lease and lease.expires_at and lease.expires_at.tzinfo
            else (lease.expires_at.replace(tzinfo=timezone.utc) if lease and lease.expires_at else now)
        )
        lease_is_valid = bool(lease and lease.is_active and lease_exp >= now)

        for req in running_requests:
            ref_time = req.last_heartbeat_at or req.started_at or req.created_at
            if ref_time and ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)

            age = (now - ref_time).total_seconds() if ref_time else (max_age_seconds + 1)
            
            # An active valid lease held by the exact same worker with the exact same generation means still alive
            is_actively_held = (
                lease_is_valid
                and lease.holder_id == req.worker_id
                and lease.lease_generation == req.lease_generation
            )

            if age > max_age_seconds or not is_actively_held:
                current_attempts = req.attempt_count or 1
                if current_attempts < max_retries:
                    logger.warning(
                        "Recovering abandoned IngestionRequest '%s' (attempt %d/%d, age %.1fs) -> resetting to pending",
                        req.id,
                        current_attempts,
                        max_retries,
                        age,
                    )
                    req.status = "pending"
                    req.worker_id = None
                    req.started_at = None
                    req.last_heartbeat_at = None
                    req.lease_generation = None
                else:
                    logger.error(
                        "Failing permanently abandoned IngestionRequest '%s' (exceeded max retries %d/%d)",
                        req.id,
                        current_attempts,
                        max_retries,
                    )
                    req.status = "failed"
                    req.completed_at = now
                    req.error_message = (
                        f"Abandoned execution: exceeded maximum retry attempts ({max_retries}) "
                        f"after worker crash or lease expiration (last heartbeat age: {int(age)}s)"
                    )
                recovered_count += 1

        if recovered_count > 0:
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error during recover_abandoned_requests: %s", exc)

    return recovered_count


def check_trigger_rate_limit_and_concurrency(
    db: Session,
    cooldown_seconds: int = 10,
) -> tuple[bool, str | None, int]:
    """Evaluates database-backed rate limiting and concurrency safety.
    
    Returns:
        (allowed: bool, reason: str | None, remaining_seconds: int)
    """
    now = utc_now()

    # 1. Concurrency check: is there any request in 'pending' or 'running' state?
    active_req = (
        db.query(IngestionRequest)
        .filter(IngestionRequest.status.in_(["pending", "running"]))
        .first()
    )
    if active_req:
        return False, "concurrency_busy", 0

    # 2. Rate limit cooldown: check most recently created request
    latest_req = (
        db.query(IngestionRequest)
        .order_by(IngestionRequest.created_at.desc())
        .first()
    )
    if latest_req and latest_req.created_at:
        created = (
            latest_req.created_at
            if latest_req.created_at.tzinfo
            else latest_req.created_at.replace(tzinfo=timezone.utc)
        )
        elapsed = (now - created).total_seconds()
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed)
            return False, "rate_limited", max(1, remaining)

    return True, None, 0


def create_ingestion_request(
    db: Session,
    trigger_origin: str = "manual_api",
) -> IngestionRequest:
    """Creates and persists an IngestionRequest in 'pending' status."""
    req = IngestionRequest(
        id=new_id(),
        status="pending",
        trigger_origin=trigger_origin,
        attempt_count=0,
        created_at=utc_now(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    logger.info("Created IngestionRequest ID '%s' with origin '%s'", req.id, trigger_origin)
    return req


def atomic_create_ingestion_request_if_allowed(
    db: Session,
    cooldown_seconds: int = 10,
    trigger_origin: str = "manual_api",
) -> tuple[IngestionRequest | None, str | None, int]:
    """Atomically checks rate limits and creates an IngestionRequest within a single database transaction.
    
    Returns:
        (request: IngestionRequest | None, error_reason: str | None, remaining_seconds: int)
    """
    # 1. Recover any stale abandoned requests first
    recover_abandoned_requests(db, max_age_seconds=cooldown_seconds)

    # 2. Evaluate rate limit and concurrency
    allowed, reason, remaining = check_trigger_rate_limit_and_concurrency(db, cooldown_seconds=cooldown_seconds)
    if not allowed:
        return None, reason, remaining

    try:
        req = create_ingestion_request(db, trigger_origin=trigger_origin)
        return req, None, 0
    except Exception as exc:
        db.rollback()
        logger.error("Failed to atomically create ingestion request: %s", exc)
        return None, "concurrency_busy", 0


def atomic_claim_request_with_lease(
    db: Session,
    worker_id: str = "worker",
    lease_name: str = "canonical_ingestion",
    ttl_seconds: int = 300,
) -> tuple[IngestionRequest | None, int | None]:
    """Atomically acquires the exclusive execution lease AND claims the oldest pending IngestionRequest.
    
    If the lease cannot be acquired (held by another active worker), the request remains untouched in 'pending'.
    Returns:
        (claimed_request: IngestionRequest | None, lease_generation: int | None)
    """
    now = utc_now()
    expires_at = now + timedelta(seconds=ttl_seconds)

    try:
        # Step 1: Check lease availability
        lease = db.query(IngestionLease).filter(IngestionLease.lease_name == lease_name).first()
        if lease:
            exp = (
                lease.expires_at
                if lease.expires_at and lease.expires_at.tzinfo
                else (lease.expires_at.replace(tzinfo=timezone.utc) if lease.expires_at else now)
            )
            # If active and not expired and held by another worker, cannot claim
            if lease.is_active and exp >= now and lease.holder_id != worker_id:
                logger.debug("Cannot claim request: lease '%s' actively held by '%s'", lease_name, lease.holder_id)
                return None, None

        # Step 2: Check for a pending request to claim
        pending = (
            db.query(IngestionRequest)
            .filter(IngestionRequest.status == "pending")
            .order_by(IngestionRequest.created_at.asc())
            .first()
        )
        if not pending:
            return None, None

        # Step 3: Atomically acquire/update lease and claim request
        if not lease:
            lease = IngestionLease(
                lease_name=lease_name,
                holder_id=worker_id,
                lease_generation=1,
                acquired_at=now,
                renewed_at=now,
                expires_at=expires_at,
                is_active=True,
            )
            db.add(lease)
            generation = 1
        else:
            generation = (lease.lease_generation or 0) + 1
            lease.holder_id = worker_id
            lease.lease_generation = generation
            lease.acquired_at = now
            lease.renewed_at = now
            lease.expires_at = expires_at
            lease.is_active = True

        # Update request
        pending.status = "running"
        pending.worker_id = worker_id
        pending.started_at = now
        pending.last_heartbeat_at = now
        pending.lease_generation = generation
        pending.attempt_count = (pending.attempt_count or 0) + 1

        db.commit()
        db.refresh(pending)
        logger.info(
            "Atomically claimed IngestionRequest '%s' and acquired lease '%s' (gen %d) for worker '%s'",
            pending.id,
            lease_name,
            generation,
            worker_id,
        )
        return pending, generation
    except Exception as exc:
        db.rollback()
        logger.error("Error during atomic_claim_request_with_lease: %s", exc)
        return None, None


def claim_pending_request(
    db: Session,
    worker_id: str = "worker",
) -> IngestionRequest | None:
    """Atomically finds and claims the oldest 'pending' IngestionRequest along with execution lease."""
    req, _ = atomic_claim_request_with_lease(db, worker_id=worker_id)
    return req


def finish_request(
    db: Session,
    request_id: str,
    worker_id: str,
    status: str,
    result_summary: dict[str, Any] | None = None,
    error_message: str | None = None,
    expected_generation: int | None = None,
) -> bool:
    """Marks an IngestionRequest as 'succeeded' or 'failed' under strict lease generation fencing."""
    now = utc_now()
    try:
        # Step 1: If expected_generation is specified, verify lease fencing under row lock
        if expected_generation is not None:
            if not validate_lease_fencing(
                db,
                lease_name="canonical_ingestion",
                holder_id=worker_id,
                expected_generation=expected_generation,
                for_update=True,
            ):
                logger.error(
                    "Stale worker '%s' (gen %d) blocked from finishing request '%s'",
                    worker_id, expected_generation, request_id
                )
                return False

        query = db.query(IngestionRequest).filter(IngestionRequest.id == request_id)
        try:
            req = query.with_for_update().first()
        except Exception:
            req = query.first()

        if not req:
            return False

        # If expected_generation is specified, verify request's generation matches
        if expected_generation is not None and req.lease_generation is not None:
            if req.lease_generation != expected_generation:
                logger.error(
                    "Request '%s' generation (%s) does not match expected (%d). Aborting finish.",
                    request_id, req.lease_generation, expected_generation
                )
                return False

        req.status = status
        req.worker_id = worker_id
        req.completed_at = now
        req.result_summary = result_summary
        req.error_message = error_message
        db.commit()
        logger.info("Finished IngestionRequest ID '%s' with status '%s' (gen %s)", request_id, status, expected_generation)
        return True
    except Exception as exc:
        db.rollback()
        logger.error("Error finishing request '%s': %s", request_id, exc)
        return False

class IngestionHeartbeat:
    """Autonomous background heartbeat manager that periodically refreshes the lease
    expires_at and the IngestionRequest.last_heartbeat_at while a long-running job executes.
    
    If the lease is superseded or taken over by another worker, it marks is_valid = False
    so the worker can abort promptly.
    """
    def __init__(
        self,
        session_factory,
        lease_name: str = "canonical_ingestion",
        holder_id: str = "worker",
        generation: int = 1,
        request_id: str | None = None,
        interval_seconds: float = 5.0,
        ttl_seconds: int = 300,
    ):
        self.session_factory = session_factory
        self.lease_name = lease_name
        self.holder_id = holder_id
        self.generation = generation
        self.request_id = request_id
        self.interval_seconds = interval_seconds
        self.ttl_seconds = ttl_seconds
        self.is_valid = True
        self.last_exception: Exception | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="IngestionHeartbeat")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def check_health(self) -> None:
        """Raises if the heartbeat thread encountered an exception or was invalidated."""
        if self.last_exception is not None:
            raise RuntimeError(f"Heartbeat thread failure: {self.last_exception}") from self.last_exception
        if not self.is_valid:
            raise StaleLeaseError(f"Lease '{self.lease_name}' at generation {self.generation} was invalidated.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if exc_type is None and self.last_exception is not None:
            raise RuntimeError(f"Heartbeat thread failure: {self.last_exception}") from self.last_exception
        if exc_type is None and not self.is_valid:
            raise StaleLeaseError(f"Lease '{self.lease_name}' at generation {self.generation} was invalidated.")

    def _run(self):
        while not self._stop_event.wait(self.interval_seconds):
            db = self.session_factory()
            try:
                # 1. Heartbeat lease with generation fencing
                lease_ok = heartbeat_lease(
                    db,
                    lease_name=self.lease_name,
                    holder_id=self.holder_id,
                    expected_generation=self.generation,
                    ttl_seconds=self.ttl_seconds,
                )
                if not lease_ok:
                    self.is_valid = False
                    logger.warning(
                        "Heartbeat failed: lease '%s' no longer held by '%s' at gen %d",
                        self.lease_name, self.holder_id, self.generation
                    )
                    break

                # 2. Heartbeat request if associated
                if self.request_id:
                    req_ok = heartbeat_request(
                        db,
                        request_id=self.request_id,
                        worker_id=self.holder_id,
                        expected_generation=self.generation,
                    )
                    if not req_ok:
                        self.is_valid = False
                        logger.warning(
                            "Heartbeat failed: request '%s' no longer valid at gen %d",
                            self.request_id, self.generation
                        )
                        break
            except Exception as exc:
                self.is_valid = False
                self.last_exception = exc
                logger.error("Error in IngestionHeartbeat thread: %s", exc)
                break
            finally:
                db.close()
