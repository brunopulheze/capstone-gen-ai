# User Persona Service

**Endpoint:** `POST /persona`

## Overview

The User Persona service generates a detailed, research-grounded UX user persona from a short guided onboarding questionnaire. The LLM produces a structured JSON persona that the frontend renders as a visual persona card.

## How It Works

```
Onboarding answers (product, audience, goals, frustrations, gender)
     │
     ▼
Build structured prompt with all inputs
     │
     ▼
Groq LLM generates persona as JSON
     │
     ▼
Strip markdown fences if present
     │
     ▼
Parse JSON + enforce user's explicit gender choice
     │
     ▼
Return persona_report
```

## Request Payload

| Field | Type | Description |
|---|---|---|
| `product_type` | `string` | The product or service being designed for |
| `audience` | `string` | Target audience description |
| `goals` | `list[string]` | Primary user goals (from guided steps) |
| `frustration` | `string` | The audience's biggest pain point |
| `gender` | `string` | Desired persona gender ("male", "female", "non-binary") |

## Persona Response

The `persona_report` field contains:

| Field | Description |
|---|---|
| `name` | Full name — unambiguously matches the requested gender |
| `age` | Age as a string (e.g. `"32"`) |
| `role` | Job title or life role |
| `location` | City, Country |
| `gender` | Enforced to match the user's input |
| `quote` | Short first-person quote (max 15 words) |
| `bio` | 2–3 sentence narrative about who this person is |
| `goals` | 3 specific goals tied to both product and audience |
| `pain_points` | 3 pain points |
| `motivations` | 3 motivations |
| `devices` | Devices they use (e.g. `["Mobile", "Laptop"]`) |
| `tech_savvy` | One of: `Low`, `Medium`, `High` |

## Gender Enforcement

Gender is treated as a hard requirement. The LLM is instructed to:
- Use an unambiguously gendered name
- Set the `gender` field exactly to the user's choice

After the LLM response is parsed, the gender field is **overwritten in code** with the original user input as a safety net, preventing any drift.

## Error Handling

If the LLM returns malformed JSON (e.g. with markdown fences), the service strips code fences with a regex before attempting `json.loads`. If parsing still fails, a friendly error message is returned asking the user to try again.

## Technology

- **LLM:** Groq `llama-3.3-70b-versatile` (temperature 0.7 for creative variety)
- **Output format:** Structured JSON
