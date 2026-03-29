"""Dashboard statistics API routes."""

from flask import Blueprint, jsonify, g
from sqlalchemy import func
from database import db, Scan, ScanResult
from auth.middleware import require_auth
from datetime import datetime, timedelta

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/stats", methods=["GET"])
@require_auth
def get_dashboard_stats():
    """Get dashboard statistics for the current user."""
    user_id = g.current_user.id

    # Total scans
    total_scans = Scan.query.filter_by(user_id=user_id).count()

    # Completed scans
    completed_scans = Scan.query.filter_by(user_id=user_id, status="completed").count()

    # Running scans
    running_scans = Scan.query.filter_by(user_id=user_id, status="running").count()

    # Average risk score
    avg_risk = db.session.query(func.avg(Scan.risk_score))\
        .filter(Scan.user_id == user_id, Scan.risk_score.isnot(None)).scalar()

    # Total profiles found
    total_profiles = db.session.query(func.sum(Scan.platforms_found))\
        .filter(Scan.user_id == user_id).scalar()

    # Total entities found
    total_entities = db.session.query(func.sum(Scan.entities_found))\
        .filter(Scan.user_id == user_id).scalar()

    # Recent scans (last 10)
    recent_scans = Scan.query.filter_by(user_id=user_id)\
        .order_by(Scan.created_at.desc()).limit(10).all()

    # Top platforms (from all results)
    scan_ids = [s.id for s in Scan.query.filter_by(user_id=user_id).all()]
    platform_counts = {}
    if scan_ids:
        results = ScanResult.query.filter(ScanResult.scan_id.in_(scan_ids)).all()
        for r in results:
            platform_counts[r.platform] = platform_counts.get(r.platform, 0) + 1

    top_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Timeline data (last 14 days)
    today = datetime.utcnow().date()
    fourteen_days_ago = today - timedelta(days=13)
    
    # Fallback to python-side filtering for db-agnostic date handling
    recent_all_scans = Scan.query.filter_by(user_id=user_id).order_by(Scan.created_at.desc()).limit(100).all()
    
    timeline = {}
    for i in range(14):
        d = today - timedelta(days=13-i)
        date_str = d.strftime("%Y-%m-%d")
        timeline[date_str] = {"scans": 0, "risk_sum": 0.0, "risk_count": 0}

    for s in recent_all_scans:
        date_str = s.created_at.strftime("%Y-%m-%d") if hasattr(s.created_at, 'strftime') else str(s.created_at)[:10]
        if date_str in timeline:
            timeline[date_str]["scans"] += 1
            if s.risk_score is not None:
                timeline[date_str]["risk_sum"] += s.risk_score
                timeline[date_str]["risk_count"] += 1

    timeline_list = []
    # Convert to list and compute average risk
    for date_str in sorted(timeline.keys()):
        data = timeline[date_str]
        avg_risk = 0.0
        if data["risk_count"] > 0:
            avg_risk = round(data["risk_sum"] / data["risk_count"], 1)
            
        timeline_list.append({
            "date": date_str,
            "scans": data["scans"],
            "avg_risk": avg_risk
        })

    return jsonify({
        "stats": {
            "total_scans": total_scans,
            "completed_scans": completed_scans,
            "running_scans": running_scans,
            "avg_risk_score": round(avg_risk, 1) if avg_risk else 0,
            "total_profiles_found": total_profiles or 0,
            "total_entities_found": total_entities or 0,
        },
        "recent_scans": [s.to_dict() for s in recent_scans],
        "top_platforms": [{"platform": p, "count": c} for p, c in top_platforms],
        "timeline": timeline_list,
    }), 200
