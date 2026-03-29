"""Layer 5: Identity Graph Builder — NetworkX graph with risk scoring + confidence."""

import json
import math
import logging
from datetime import datetime, timezone
import networkx as nx
from .confidence import ConfidenceScorer

logger = logging.getLogger(__name__)


# Risk level weights
RISK_WEIGHTS = {
    "phone_public": 9.0,
    "email_public": 6.0,
    "real_name_linked": 4.0,
    "username_multiple_platforms": 3.0,
    "social_profile_found": 2.0,
    "dev_profile_found": 1.5,
    "name_mention": 1.0,
    "breach_found": 10.0,
}

# Node type colors for Cytoscape.js
NODE_COLORS = {
    "name": "#8b5cf6",       # Purple
    "email": "#3b82f6",      # Blue
    "phone": "#ef4444",      # Red
    "username": "#10b981",   # Green
    "platform": "#f59e0b",   # Amber
    "url": "#6b7280",        # Gray
    "repository": "#ec4899", # Pink
    "breach": "#dc2626",     # Red
    "metadata": "#14b8a6",   # Teal
    "document": "#06b6d4",   # Cyan
    "event": "#a855f7",      # Violet
}

NODE_SHAPES = {
    "name": "diamond",
    "email": "round-rectangle",
    "phone": "triangle",
    "username": "ellipse",
    "platform": "hexagon",
    "url": "rectangle",
    "repository": "barrel",
    "breach": "octagon",
    "metadata": "tag",
    "document": "round-rectangle",
    "event": "star",
}


class IdentityGraphBuilder:
    """Builds a NetworkX graph from extracted entities and computes risk scores."""

    def __init__(self):
        self.graph = nx.Graph()
        self.risk_events = []

    def add_identity_node(self, node_id, node_type, label, **metadata):
        """Add an identity node (email, username, name, phone, platform)."""
        node_metadata = dict(metadata)
        node_color = node_metadata.pop("color", NODE_COLORS.get(node_type, "#6b7280"))
        node_shape = node_metadata.pop("shape", NODE_SHAPES.get(node_type, "ellipse"))
        node_metadata.pop("id", None)
        node_metadata.pop("label", None)
        node_metadata.pop("node_type", None)

        self.graph.add_node(
            node_id,
            node_type=node_type,
            label=label,
            color=node_color,
            shape=node_shape,
            **node_metadata,
        )

    def add_relationship(self, source_id, target_id, relationship, confidence=0.5):
        """Add an edge between two identity nodes."""
        self.graph.add_edge(
            source_id,
            target_id,
            relationship=relationship,
            confidence=confidence,
        )

    def build_from_scan_results(self, target_name, target_email, target_username, results, entities_list):
        """Build the full identity graph from scan results and extracted entities."""

        # === Central node: the target identity ===
        name_id = f"name:{target_name.lower()}"
        self.add_identity_node(name_id, "name", target_name, central=True)

        if target_email:
            email_id = f"email:{target_email.lower()}"
            self.add_identity_node(email_id, "email", target_email)
            self.add_relationship(name_id, email_id, "owns", confidence=1.0)

        if target_username:
            uname_id = f"username:{target_username.lower()}"
            self.add_identity_node(uname_id, "username", target_username)
            self.add_relationship(name_id, uname_id, "uses", confidence=1.0)

        # === Add discovered platforms ===
        for result in results:
            platform = result.get("platform", "unknown")
            url = result.get("url", "")
            username = result.get("username", "")
            confidence = result.get("confidence", 0.5)
            rich_data = result.get("rich_data", {})

            platform_id = f"platform:{platform.lower()}:{username.lower()}"
            
            # Extract primitive rich properties to inject into the platform node directly
            platform_meta = {
                k: v for k, v in rich_data.items() 
                if v and not isinstance(v, (list, dict))
            }
            
            self.add_identity_node(
                platform_id, "platform", f"{platform}",
                url=url, username=username, **platform_meta
            )
            
            # --- Rich Nodes Expansion ---
            # Create sub-nodes for list-based rich data (e.g. repositories)
            if "repositories" in rich_data:
                for repo in rich_data["repositories"]:
                    repo_url = repo.get("url", "")
                    if repo_url:
                        repo_id = f"repo:{repo_url}"
                        self.add_identity_node(
                            repo_id, "repository", repo.get("name", "Unknown Repo"),
                            url=repo_url, description=repo.get("description", ""), language=repo.get("language", "")
                        )
                        self.add_relationship(platform_id, repo_id, "owns_repo", confidence=1.0)

            # Link to username
            if username:
                uname_id = f"username:{username.lower()}"
                if not self.graph.has_node(uname_id):
                    self.add_identity_node(uname_id, "username", username)
                self.add_relationship(uname_id, platform_id, "found_on", confidence=confidence)

                # If this username matches the target's, increase confidence
                if target_username and username.lower() == target_username.lower():
                    self.add_relationship(name_id, platform_id, "confirmed_on", confidence=0.9)

            # Link to name
            self.add_relationship(name_id, platform_id, "associated_with", confidence=confidence)

            # Track risk events
            category = result.get("category", "other")
            if category == "social":
                self.risk_events.append(("social_profile_found", platform, url))
            elif category == "developer":
                self.risk_events.append(("dev_profile_found", platform, url))
                
            # Process HIBP Data
            if "breaches" in rich_data:
                for breach in rich_data["breaches"]:
                    breach_name = breach.get("name", "Unknown Breach")
                    breach_id = f"breach:{breach_name}"
                    self.add_identity_node(
                        breach_id, "breach", breach_name,
                        date=breach.get("date"), domain=breach.get("domain"),
                        data_classes=",".join(breach.get("data_classes", []))
                    )
                    self.add_relationship(platform_id, breach_id, "exposed_in", confidence=1.0)
                    
                    if username:
                        email_node_id = f"email:{username.lower()}"
                        if not self.graph.has_node(email_node_id):
                            self.add_identity_node(email_node_id, "email", username)
                        self.add_relationship(email_node_id, breach_id, "compromised_in", confidence=1.0)
                        
                    self.risk_events.append(("breach_found", breach_name, f"Date: {breach.get('date')}"))

        # === Add extracted entities ===
        for entity_set in entities_list:
            source_url = entity_set.get("url", "") if isinstance(entity_set, dict) else entity_set.url
            entities = entity_set if isinstance(entity_set, dict) else entity_set.to_dict()

            # Emails found
            for email in entities.get("emails", []):
                email_id = f"email:{email.lower()}"
                if not self.graph.has_node(email_id):
                    self.add_identity_node(email_id, "email", email)
                self.add_relationship(name_id, email_id, "linked_to", confidence=0.6)
                self.risk_events.append(("email_public", email, source_url))

            # Phones found
            for phone in entities.get("phones", []):
                phone_id = f"phone:{phone}"
                if not self.graph.has_node(phone_id):
                    self.add_identity_node(phone_id, "phone", phone)
                self.add_relationship(name_id, phone_id, "linked_to", confidence=0.7)
                self.risk_events.append(("phone_public", phone, source_url))

            # Handles found
            for handle in entities.get("handles", []):
                handle_id = f"username:{handle.lower()}"
                if not self.graph.has_node(handle_id):
                    self.add_identity_node(handle_id, "username", f"@{handle}")
                self.add_relationship(name_id, handle_id, "associated_with", confidence=0.4)

            # Cross-platform usernames
            for platform, username in entities.get("platform_usernames", {}).items():
                plat_id = f"platform:{platform}:{username.lower()}"
                if not self.graph.has_node(plat_id):
                    self.add_identity_node(plat_id, "platform", platform, username=username)
                    uname_id = f"username:{username.lower()}"
                    if not self.graph.has_node(uname_id):
                        self.add_identity_node(uname_id, "username", username)
                    self.add_relationship(uname_id, plat_id, "found_on", confidence=0.6)
                self.add_relationship(name_id, plat_id, "linked_to", confidence=0.5)

    def calculate_risk_score(self):
        """Calculate an overall risk score from 0-10."""
        score = 0.0
        for event_type, detail, source in self.risk_events:
            weight = RISK_WEIGHTS.get(event_type, 1.0)
            score += weight

        # Normalize to 0-10 scale with diminishing returns
        normalized = min(10.0, score / (1.0 + score / 10.0) * 2)
        return round(normalized, 1)

    def get_risk_level(self, score):
        """Convert numeric score to risk level string."""
        if score >= 8.0:
            return "critical"
        elif score >= 6.0:
            return "high"
        elif score >= 3.0:
            return "medium"
        return "low"

    def get_centrality_analysis(self):
        """Identify the most connected nodes (highest exposure points)."""
        if not self.graph.nodes():
            return []

        centrality = nx.degree_centrality(self.graph)
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)

        analysis = []
        for node_id, score in sorted_nodes[:10]:
            node_data = self.graph.nodes[node_id]
            analysis.append({
                "node_id": node_id,
                "label": node_data.get("label", node_id),
                "type": node_data.get("node_type", "unknown"),
                "centrality": round(score, 3),
                "connections": self.graph.degree(node_id),
            })
        return analysis

    def to_cytoscape_json(self):
        """Export the graph in Cytoscape.js-compatible JSON format."""
        elements = {"nodes": [], "edges": []}

        for node_id, data in self.graph.nodes(data=True):
            node_data = {
                "data": {
                    "id": node_id,
                    "label": data.get("label", node_id),
                    "type": data.get("node_type", "unknown"),
                    "color": data.get("color", "#6b7280"),
                    "shape": data.get("shape", "ellipse"),
                }
            }
            # Add extra metadata dynamically (skip reserved keys)
            reserved_keys = {"label", "node_type", "color", "shape", "central"}
            for key, val in data.items():
                if key not in reserved_keys:
                    node_data["data"][key] = val
                    
            if data.get("central"):
                node_data["data"]["central"] = True
                
            elements["nodes"].append(node_data)

        for source, target, data in self.graph.edges(data=True):
            elements["edges"].append({
                "data": {
                    "source": source,
                    "target": target,
                    "relationship": data.get("relationship", "related"),
                    "confidence": data.get("confidence", 0.5),
                }
            })

        return elements

    def get_summary_stats(self):
        """Get summary statistics of the graph."""
        node_types = {}
        for _, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "unknown")
            node_types[nt] = node_types.get(nt, 0) + 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": node_types,
            "risk_events": len(self.risk_events),
        }
