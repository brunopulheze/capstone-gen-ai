# Scope Project Service

**Endpoint:** `POST /scope-project`  
**Palette regeneration:** `POST /regenerate-palette`

## Overview

The Scope Project service transforms a client's guided onboarding answers into a structured project scope document. It performs a contradiction check on the user's input, optionally scrapes competitor URLs for market context, generates a brand colour palette from style preferences, and returns a full JSON scope document.

## How It Works

```
Onboarding answers (business type, project type, features, timeline, description)
     │
     ▼
Step 1 — Pre-flight contradiction check (LLM)
     │    Compares structured answers vs. free-text description
     │    Returns: {has_conflict: bool, question: string}
     │
     ├── Conflict detected ──► return clarifying question to the user
     │
     └── No conflict ──► continue
          │
          ▼
Step 2 — Competitor URL scraping (optional, up to 3 URLs)
     │    Reuses the UX Audit scraper (httpx + BeautifulSoup)
     │    Extracts page text to build competitive context
     │
     ▼
Step 3 — Scope document generation (LLM)
     │    Combines all inputs + competitor context + brand preferences
     │    Returns structured JSON scope document
     │
     ▼
Scope document returned
```

## Request Payload

| Field | Type | Description |
|---|---|---|
| `business_type` | `string` | e.g. "E-commerce", "SaaS startup" |
| `project_type` | `string` | e.g. "Mobile app", "AI chatbot" |
| `features` | `list[string]` | Selected feature list from guided steps |
| `timeline` | `string` | e.g. "3 months", "ASAP" |
| `description` | `string` | Free-text description from the user |
| `clarification` | `string` | User's answer to a contradiction question (if any) |
| `competitor_urls` | `list[string]` | Up to 3 URLs to scrape for competitor context |
| `brand_preferences` | `string` | Free-text style / colour preferences |

## Scope Document Response

The `scope_report` field in the response contains:

| Field | Description |
|---|---|
| `project_type` | Descriptive project title |
| `overview` | 2–3 sentence plain-English description |
| `features` | List of features |
| `tech_stack` | Recommended stack with rationale for each choice |
| `timeline` | Realistic estimated timeline |
| `next_steps` | 3 immediate action items |
| `extra_notes` | Any additional observations |
| `competitor_insights` | 2–3 sentence summary of competitor findings |
| `brand_notes` | Colour/style direction summary |
| `color_palette` | 5 colour swatches `[{hex, name}]` |

## Colour Palette

- If `brand_preferences` are provided, the LLM derives the palette from those preferences.
- If not, it generates a palette appropriate to the industry/project type.
- Always returns exactly 5 swatches.
- The palette can be regenerated independently via `POST /regenerate-palette` without re-running the full scope.

## Contradiction Check

Before generating the scope, the LLM compares the structured form answers against the free-text description. Minor additions are not flagged — only meaningful conflicts (e.g. "Mobile app" selected but description says "desktop software only"). If a conflict is found, a single clarifying question is returned and scope generation is paused until the user responds.

## Technology

- **LLM:** Groq (`llama-3.3-70b-versatile`, temperature 0.4)
- **Web scraping:** Reuses `_scrape_url` from the UX Audit service
- **Output format:** Structured JSON validated with `json.loads`
