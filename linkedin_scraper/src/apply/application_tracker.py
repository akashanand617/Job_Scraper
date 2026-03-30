"""
Application tracking for the Auto-Apply module.
Tracks job applications with status, notes, and event history.
"""

from collections import Counter
from datetime import datetime
from typing import Optional, List, Dict

from . import db
from .models import (
    Application,
    ApplicationStatus,
    ApplicationEvent,
    ApplicationCreateRequest,
    ApplicationUpdateRequest,
)


class ApplicationTracker:
    """Tracks job applications in DynamoDB with event logging."""

    def create(self, user_id: str, request: ApplicationCreateRequest) -> Application:
        """Start tracking a job application."""
        app = Application(
            user_id=user_id,
            job_id=request.job_id,
            status=request.status or ApplicationStatus.INTERESTED,
            notes=request.notes,
            events=[
                ApplicationEvent(
                    event_type="created",
                    details=f"Application tracking started with status: {request.status or 'interested'}",
                )
            ],
        )
        db.put_item(db.APPLICATIONS_TABLE, app.model_dump())
        return app

    def get(self, user_id: str, job_id: str) -> Optional[Application]:
        """Get a specific tracked application."""
        item = db.get_item(db.APPLICATIONS_TABLE, {"user_id": user_id, "job_id": job_id})
        if item:
            return Application(**item)
        return None

    def list_for_user(self, user_id: str, status: Optional[str] = None) -> List[Application]:
        """List all applications for a user, optionally filtered by status."""
        items = db.query_items(db.APPLICATIONS_TABLE, "user_id", user_id)
        apps = [Application(**item) for item in items]

        if status:
            apps = [a for a in apps if a.status.value == status]

        # Sort by most recently updated
        apps.sort(key=lambda a: a.updated_at, reverse=True)
        return apps

    def update(self, user_id: str, job_id: str, request: ApplicationUpdateRequest) -> Optional[Application]:
        """Update an application's status, notes, or follow-up date."""
        app = self.get(user_id, job_id)
        if not app:
            return None

        events = []

        if request.status and request.status != app.status:
            events.append(ApplicationEvent(
                event_type="status_change",
                details=f"Status changed from {app.status.value} to {request.status.value}",
            ))
            app.status = request.status

            # Set applied_at when status changes to applied
            if request.status == ApplicationStatus.APPLIED and not app.applied_at:
                app.applied_at = datetime.now().isoformat()

        if request.notes is not None and request.notes != app.notes:
            events.append(ApplicationEvent(
                event_type="note_updated",
                details=request.notes[:200],
            ))
            app.notes = request.notes

        if request.follow_up_date is not None:
            app.follow_up_date = request.follow_up_date

        if request.applied_via is not None:
            app.applied_via = request.applied_via

        if events:
            app.events.extend(events)
            app.updated_at = datetime.now().isoformat()
            db.put_item(db.APPLICATIONS_TABLE, app.model_dump())

        return app

    def delete(self, user_id: str, job_id: str) -> bool:
        """Stop tracking an application."""
        return db.delete_item(db.APPLICATIONS_TABLE, {"user_id": user_id, "job_id": job_id})

    def get_stats(self, user_id: str) -> Dict:
        """Get application statistics for a user."""
        apps = self.list_for_user(user_id)

        status_counts = Counter(a.status.value for a in apps)
        total = len(apps)
        applied = sum(1 for a in apps if a.applied_at)

        # Response rate: interviews / applied
        interviews = status_counts.get("interviewing", 0)
        response_rate = (interviews / applied * 100) if applied > 0 else 0.0

        # Offers
        offers = status_counts.get("offered", 0) + status_counts.get("accepted", 0)
        offer_rate = (offers / applied * 100) if applied > 0 else 0.0

        return {
            "total_tracked": total,
            "applied": applied,
            "status_breakdown": dict(status_counts),
            "response_rate": round(response_rate, 1),
            "offer_rate": round(offer_rate, 1),
            "most_recent": apps[0].model_dump() if apps else None,
        }
