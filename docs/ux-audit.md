# UX Audit Service

**Endpoint:** `POST /upload` (with `service_mode: "ux-audit"`)

## Overview

The UX Audit service performs a structured accessibility and UX review via two input modes — a public URL or an uploaded screenshot. Both modes use a **Reflexion loop** to self-critique and improve the initial audit against a WCAG 2.2 checklist before returning the final report.

## Input Modes

### 1. URL Mode
The service scrapes the public page using `httpx` + `BeautifulSoup`, extracts meaningful text content (up to 12,000 characters), and passes it to the LLM for analysis.

### 2. Image Mode (Multimodal)
An uploaded screenshot is base64-encoded and passed directly to Groq's vision-capable model (`llama-4-scout-17b-16e-instruct`) for visual UX review.

## How It Works

```
Input: URL or screenshot
     │
     ├── URL ──► httpx scrape ──► BeautifulSoup text extraction (max 12k chars)
     │
     └── Image ──► base64 encode ──► Groq vision LLM
     │
     ▼
Initial UX audit report (structured Markdown)
     │
     ▼
┌─────────────────────── Reflexion Loop ──────────────────────┐
│  Step 1 — Critique                                          │
│    WCAG 2.2 expert LLM checks coverage gaps against         │
│    a 10-point checklist (contrast, keyboard nav, ARIA, etc) │
│                                                             │
│  Step 2 — Tavily search (only if gaps found)                │
│    Fetches targeted WCAG reference material from:           │
│    w3.org · webaim.org · developer.mozilla.org              │
│                                                             │
│  Step 3 — Revision                                          │
│    Primary LLM rewrites the audit incorporating the gaps    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
Final audit report returned as Markdown
```

## Audit Report Structure

The LLM is prompted to return the report with exactly these sections:

| Section | Content |
|---|---|
| `## Summary` | 2–3 sentences on overall UX quality |
| `## Visual Hierarchy` | Bullet list with ❌ / ⚠️ / ✅ icons |
| `## Accessibility` | WCAG failures, contrast, alt text, keyboard nav, ARIA |
| `## Navigation & Information Architecture` | Menus, labels, breadcrumbs, wayfinding |
| `## CTAs & Conversion` | Button clarity, placement, copy, friction |
| `## Typography & Readability` | Font size, line length, contrast, heading hierarchy |
| `## Quick Wins` | Numbered list of 3–5 highest-impact actionable improvements |

## WCAG 2.2 Critique Checklist

The self-critique step checks for all of these:

- Colour contrast ratios (AA: 4.5:1 text, 3:1 UI components)
- Keyboard navigation and visible focus indicators
- ARIA roles, labels, and landmark regions
- Alt text for all images and icon-only buttons
- Touch target sizes (minimum 44×44 px)
- Form labels, inline error messages, and validation feedback
- Heading hierarchy (no skipped levels)
- Descriptive link text (no "click here")
- Motion and animation safety (`prefers-reduced-motion`)
- Screen reader reading order and semantic HTML

## File Limits

| Limit | Value |
|---|---|
| Max image size | 10 MB |
| Supported formats | PNG, JPG, JPEG, WebP, GIF |
| Max page scrape | 12,000 characters |
| Scrape timeout | 12 seconds |

## Technology

- **Web scraping:** `httpx`, `BeautifulSoup`
- **Vision LLM:** Groq `meta-llama/llama-4-scout-17b-16e-instruct`
- **Critique LLM:** `state.llm_quick`
- **Web search:** Tavily (w3.org, webaim.org, developer.mozilla.org)
