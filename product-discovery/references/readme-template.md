# README.md Template

Save this file as `README.md` in the project root. Follow this format exactly.

## Purpose

The README is the human-facing document. It contains what CLAUDE.md deliberately excludes: rationale, product context, and setup instructions. At project start this is short. It grows as the project grows.

## Required sections

1. **Top-level heading** (`#`) with the project name, followed by a one-paragraph description of what the product does and why.
2. `## Getting started` -- Prerequisites, setup steps, and how to run the project.
3. `## Product decisions` -- Key decisions with rationale. Each decision is a bold label followed by an explanation of why that choice was made.

## Complete example

```markdown
# SalesSync

A dashboard that pre-computes daily Salesforce pipeline summaries so a sales manager can walk into standup with yesterday's numbers already on screen.

## Getting started

### Prerequisites

- Node.js 18+
- Salesforce developer account with API access

### Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in Salesforce credentials
3. Run `npm install`

### Running

\`\`\`bash
npm run dev
\`\`\`

## Product decisions

- **SQLite over Postgres**: This is a single-user local prototype. SQLite avoids setup friction and is sufficient for the data volume (dozens of records per day).
- **Server-side Salesforce calls**: API credentials must stay secret. Client-side calls would expose them.
- **Auth deferred**: Only two test users for now. Auth is a later step once the core workflow is validated.
```
