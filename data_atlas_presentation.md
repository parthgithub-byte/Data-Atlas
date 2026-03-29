# Data Atlas: Digital Footprint and Data Exposure Detection Platform
A privacy-first Open Source Intelligence (OSINT) tool designed for digital footprint discovery, analysis, and personal risk assessment.

---

## Meet the Team
Development was a collaborative endeavor, with each member driving core functionalities:
* **Parth Pakhare (TCOB01)** & **Omkar Shelar (TCOB41)**: Led System Design, Architecture, Data Flow Modeling, core improvements, and system benefits mapping.
* **Soham Sadakal (TCOB16)**: Spearheaded Frontend Development, User Interface/UX design, and core interactive ideas.
* **Kaushal Pokarne (TCOB11)**: Managed Project Documentation, technical reporting, and requirements specification.
* **Omkar Shelar (TCOB41)**: Managed overall team roles, coordination, and provided crucial cross-functional assistance in every development field.
* **Overall Development**: Jointly executed across the stack by all team members.

---

## The Digital Privacy Problem
* **Data Breach Epidemic:** Over 10 billion records exposed globally. Most individuals are unaware of their digital footprint.
* **Username Reuse:** Predictable handles allow trivial cross-platform correlation by adversaries.
* **Social Engineering:** Publicly available data (like phone numbers and emails) serve as serious attack vectors for phishing.
* **The Tooling Gap:** Existing OSINT tools target professional investigators, lacking ethical, self-service options for end-users.

---

## What is Data Atlas?
Data Atlas empowers individuals to audit their own digital footprint ethically.
* **Self-Scan-Policy:** Users are strictly restricted to querying their own verified identity.
* **Minimal Input, Maximum Output:** Takes Name, Email, Username, Phone, and Address to scout the web.
* **Broad Discovery:** Automatically discovers personal data across 34+ major online platforms alongside SearxNG meta-search.

---

## Goals and Objectives
* **Automated Discovery:** Concurrently enumerate usernames across platforms in under 30 seconds.
* **Deep Investigation:** Web scrape, clean, and extract entities (emails, links) from discovered pages.
* **Confidence Scoring:** Intelligently distinguish true matches from false positives using a weighted signals model.
* **Interactive Visualization:** Render graph models to map how identity pivots interact.
* **Risk Assessment:** Quantify digital exposure with a normalized 0–10 risk score and generate actionable reports.

---

## System Architecture: The 6-Layer Pipeline
1. **Layer 1: Normalizer** - Transforms base inputs into username variants and search 'dorks'.
2. **Layer 2: Discovery** - Performs asynchronous enumeration and SearxNG meta-search.
3. **Layer 3: Scraper** - Retrieves HTML, bypasses basic blocks, and extracts forensic metadata (e.g., EXIF).
4. **Layer 4: Extractor** - Uses Regex algorithms to pinpoint specific PII (Emails, Phones, Handles).
5. **Layer 5: Graph Builder** - Employs NetworkX to map connections between identity nodes.
6. **Layer 6: Reporter** - Synthesizes graph data into structured PDF/JSON risk reports.

---

## Understanding the Identity Graph 
The Identity Graph is the visual engine of Data Atlas, translating raw data into an actionable intelligence map.
* **Backend Processing (`NetworkX`):** The Python `NetworkX` library is used strictly server-side to build undirected networks where "entities" (Emails, Usernames, Phones) are connected as nodes via weighted edges (confidence ratings). NetworkX enables mathematical risk calculation, structural analysis, and centrality scoring.
* **Frontend Visualization (`Cytoscape.js`):** The JSON output from NetworkX is intercepted by the browser and rendered into an interactive canvas using `Cytoscape.js`. 
* **Significance & Working:** It visually connects abstracted dots. A user can instantly see how a single username links a professional GitHub account to an exposed "Have I Been Pwned" email breach through overlapping edge connections. 

---

## Technical Optimizations & Stealth
To ensure reliable background processing without triggering security blocks:
* **Stealth Evasion:** Rotates across 24 realistic browser User-Agents, applies randomized headers, and uses cache-busting logic.
* **Concurrency:** Employs asynchronous `httpx` and limits concurrent connections via semaphores (max 20) to prevent IP rate-limiting.
* **Fault Tolerance:** Graceful failure handling ensures the pipeline does not crash if a single platform times out.

---

## Fully Implemented Security Guardrails
The application applies enterprise-grade security within its core stack:
* **Stateless Secure Authentication:** Implemented via `HttpOnly` JWT cookies (preventing XSS exploitation). Total avoidance of vulnerable browser `localStorage`.
* **CSRF Mitigation:** Mandates verifiable CSRF-tokens for any state-mutating requests.
* **Federated Identity:** Seamless, zero-trust OAuth 2.0 integration via Google and India’s DigiLocker APIs.
* **Data Breach Check Engine:** Employs the targeted HaveIBeenPwned (HIBP) API logic to safely cross-reference user emails against massive historical leaks.

---

## Active Technology Stack
* **Backend Framework:** Python 3.10+, Flask, SQLAlchemy ORM
* **Embedded Database:** SQLite (Current data store utilizing single-file DB tracking config).
* **Queue & Cache:** Celery background worker orchestration backed natively by Redis.
* **OSINT & Intelligence:** SearxNG, httpx, BeautifulSoup4.
* **Data Science & Graphing:** NetworkX, Cytoscape.js.
* **Embedded DevOps:** Containerized stack using Docker Compose, actively monitored by GitHub Actions workflows (`.github/workflows`) for CI/CD checks.

---

## Conclusion & Future Scope
* **Conclusion:** Data Atlas successfully bridges the gap between professional OSINT capabilities and individual privacy rights, functioning as a robust self-service audit platform.
* **Future Work:**
  * Implement spaCy (NLP) for intelligent context entity extraction.
  * Integration with Dark Web (.onion) monitoring networks.
  * Image Perceptual Hashing for cross-platform avatar correlation.
  * **Database Scale-Up:** Migrate the existing `SQLite` backend logic to `PostgreSQL` to support highly parallel throughput required for enterprise use cases.
