"""Layer 6: Report Generator — Risk reports and exposure summaries."""

from datetime import datetime, timezone


class ReportGenerator:
    """Generate structured risk reports from identity graph data."""

    RISK_DESCRIPTIONS = {
        "phone_public": {
            "title": "Phone Number Exposed",
            "severity": "critical",
            "description": "A phone number was found publicly accessible on the internet.",
            "recommendation": "Contact the platform to request removal. Consider changing your phone number if it appears on multiple sites.",
        },
        "email_public": {
            "title": "Email Address Exposed",
            "severity": "high",
            "description": "An email address was found on a public webpage or profile.",
            "recommendation": "Use email aliasing services (like SimpleLogin or Apple Hide My Email) for public-facing accounts.",
        },
        "real_name_linked": {
            "title": "Real Name Linked to Accounts",
            "severity": "medium",
            "description": "Your real name is linked to online accounts, making it easy to track your digital presence.",
            "recommendation": "Consider using pseudonyms on non-professional platforms.",
        },
        "username_multiple_platforms": {
            "title": "Username Reuse Detected",
            "severity": "medium",
            "description": "The same username was found across multiple platforms, allowing easy cross-referencing.",
            "recommendation": "Use unique usernames per platform to reduce cross-platform tracking.",
        },
        "social_profile_found": {
            "title": "Social Media Profile Found",
            "severity": "low",
            "description": "A public social media profile was discovered.",
            "recommendation": "Review your privacy settings on this platform.",
        },
        "dev_profile_found": {
            "title": "Developer Profile Found",
            "severity": "low",
            "description": "A developer-oriented profile was discovered.",
            "recommendation": "Ensure no sensitive information (API keys, personal emails) is in your public repos.",
        },
    }

    @classmethod
    def generate_report(cls, graph_builder, scan_data):
        """Generate a complete risk report."""
        risk_score = graph_builder.calculate_risk_score()
        risk_level = graph_builder.get_risk_level(risk_score)
        centrality = graph_builder.get_centrality_analysis()
        stats = graph_builder.get_summary_stats()

        # Group risk events by type
        event_groups = {}
        for event_type, detail, source in graph_builder.risk_events:
            if event_type not in event_groups:
                event_groups[event_type] = []
            event_groups[event_type].append({
                "detail": detail,
                "source": source,
            })

        # Build findings
        findings = []
        for event_type, events in event_groups.items():
            template = cls.RISK_DESCRIPTIONS.get(event_type, {
                "title": event_type.replace("_", " ").title(),
                "severity": "low",
                "description": "An identity element was found online.",
                "recommendation": "Review your privacy settings.",
            })
            findings.append({
                "type": event_type,
                "title": template["title"],
                "severity": template["severity"],
                "description": template["description"],
                "recommendation": template["recommendation"],
                "occurrences": len(events),
                "details": events[:5],  # Limit to top 5 examples
            })

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: severity_order.get(f["severity"], 4))

        # Generate summary text
        summary = cls._generate_summary(risk_score, risk_level, stats, findings)

        report = {
            "scan_id": scan_data.get("scan_id"),
            "target_name": scan_data.get("target_name"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "summary": summary,
            "statistics": stats,
            "findings": findings,
            "top_exposure_points": centrality[:5],
            "recommendations": cls._generate_recommendations(findings),
        }

        return report

    @classmethod
    def _generate_summary(cls, risk_score, risk_level, stats, findings):
        """Generate a human-readable summary paragraph."""
        platform_count = stats.get("node_types", {}).get("platform", 0)
        email_count = stats.get("node_types", {}).get("email", 0)
        phone_count = stats.get("node_types", {}).get("phone", 0)

        critical_count = sum(1 for f in findings if f["severity"] == "critical")
        high_count = sum(1 for f in findings if f["severity"] == "high")

        summary_parts = [
            f"Digital footprint analysis identified {platform_count} platform(s) associated with this identity.",
        ]

        if email_count > 0:
            summary_parts.append(f"{email_count} email address(es) were found publicly accessible.")
        if phone_count > 0:
            summary_parts.append(f"{phone_count} phone number(s) were found exposed online.")

        if critical_count > 0:
            summary_parts.append(
                f"⚠️ {critical_count} CRITICAL finding(s) require immediate attention."
            )
        elif high_count > 0:
            summary_parts.append(
                f"There are {high_count} high-severity finding(s) that should be reviewed."
            )
        else:
            summary_parts.append("No critical exposures were detected.")

        summary_parts.append(f"Overall risk score: {risk_score}/10 ({risk_level.upper()}).")

        return " ".join(summary_parts)

    @classmethod
    def _generate_recommendations(cls, findings):
        """Generate actionable recommendations based on findings."""
        recommendations = []
        seen = set()

        for finding in findings:
            rec = finding["recommendation"]
            if rec not in seen:
                seen.add(rec)
                recommendations.append({
                    "priority": finding["severity"],
                    "action": rec,
                    "related_finding": finding["title"],
                })

        return recommendations
