---
name: product-evolution
description: When a product outgrows its build plan, restructure coordination artifacts for operational maturity. Replace the linear step sequence with priority-based work management, add architecture and decision documentation, and shift to a lighter operating loop. Use when BUILD_PLAN.md has 10+ completed steps, new work is mostly independent, or the user spends more time maintaining the plan than following it. Do NOT use for projects that have not reached a working core product.
---

# Product Evolution

When a product outgrows its build plan, restructure the coordination artifacts for operational maturity. Replace the linear step sequence with priority-based work management, add architecture and decision documentation, and shift from step-by-step approval to a lighter operating loop focused on coherence and regression safety.

## When to use this

This skill picks up where product-startup and project-onboarding leave off. Use it when:

- BUILD_PLAN.md has 10+ completed steps and keeps getting reorganized
- New work is mostly independent -- features, fixes, and improvements can happen in any order
- The user spends more time maintaining the plan than following it
- The codebase has enough mass that "where does this go?" matters more than "what do I build next?"
- The product works. The question is no longer "does it work?" but "how do I make it better without breaking it?"

Do not use this for projects that have not reached a working core product. If the fundamental interaction does not work yet, stay in the build loop.

## Phase 1: Maturity Assessment

Read the existing artifacts and codebase before changing anything.

### 1.1 Read the current state

Read all existing coordination artifacts:
- AGENTS.md
- BUILD_PLAN.md
- Any /docs/ directory contents
- DECISIONS.md, ARCHITECTURE.md, CHANGELOG.md if they exist

### 1.2 Assess maturity signals

Evaluate the project against these indicators:

**Ready to graduate** (most of these should be true):
- Core product interaction works and has been validated by the user
- Multiple completed build steps with accumulated notes
- Remaining steps are mostly independent of each other
- Conventions section in AGENTS.md has 5+ entries
- The codebase has clear, repeated patterns
- New work is "add X to the product" not "make the product work"

**Not ready** (any of these means stay in build mode):
- Core interaction is incomplete or unvalidated
- Remaining steps have hard sequential dependencies
- Codebase is still finding its patterns
- Fewer than 5 completed build steps

Present the assessment to the user. If the project is not ready, say so directly and explain what needs to happen first.

### 1.3 Codebase health check

Before restructuring, assess what has accumulated:

- **Test coverage**: What is tested, what is not? Where are the gaps?
- **Tech debt**: Pattern inconsistencies, TODO comments, workarounds, deprecated dependencies
- **Dead code**: Features started but abandoned, commented-out blocks, unused imports
- **Architecture strain**: Where is the current structure limiting what the product needs to do next?

This feeds directly into the ROADMAP's initial backlog.

## Phase 2: Direction Conversation

Short and targeted. The user has been building this product -- they do not need discovery questions. Ask one question at a time. Wait for the answer before moving to the next.

### 2.1 What's working

Ask: **"What's the strongest part of this product right now? What are you (or your users) getting value from?"**

This identifies what to protect. Mature product development is as much about not breaking what works as it is about adding new things.

### 2.2 What's next

Ask: **"What are the 2-3 most important things this product needs in the next month?"**

Not a feature wishlist. The short list of things that matter most right now. These seed the NOW bucket.

### 2.3 What's dragging

Ask: **"What's the most annoying thing about working in this codebase right now?"**

Tech debt, missing tooling, slow builds, confusing structure, fragile tests. These go into the roadmap as first-class work items, not afterthoughts.

## Phase 3: Restructure Artifacts

### 3.1 ROADMAP.md (replaces BUILD_PLAN.md)

The linear build plan dies here. Replace it with priority-bucketed work management.

Read `references/roadmap-template.md` for the exact format. Follow it precisely.

### 3.2 Evolve AGENTS.md

The startup AGENTS.md is minimal by design. At maturity, AGENTS.md needs to carry more weight.

Read `references/agents-md-evolved-template.md` for the exact format. Follow it precisely.

Also ensure a CLAUDE.md exists in the project root containing only:

```
@agents.md
```

This keeps the actual content in a tool-agnostic file that works across AI coding assistants, while Claude Code imports it automatically via the stub.

**Key differences from startup AGENTS.md:**
- "Build protocol" becomes "Work protocol" referencing ROADMAP.md
- Adds "Architecture overview" pointing to ARCHITECTURE.md
- Adds "Module guide" for codebases too large to read entirely
- Adds "Known issues" for broken/fragile things not yet fixed
- "Decisions" section replaced with pointer to DECISIONS.md
- Conventions section is more prescriptive with "because" rationale

### 3.3 ARCHITECTURE.md (new artifact)

This document exists because the codebase is now too complex for AGENTS.md's project structure section to convey how the system works. AGENTS.md says WHERE things are. ARCHITECTURE.md says HOW they fit together.

Read `references/architecture-template.md` for the exact format. Follow it precisely.

Keep this document accurate. An outdated architecture doc is worse than none -- it gives the AI confidence in a wrong mental model. Update it when the system's structure changes, not when individual features are added within the existing structure.

### 3.4 DECISIONS.md (new artifact)

A running log of decisions that matter. The bar for inclusion: "Would someone working on this codebase in 3 months need to know this, and would they not be able to figure it out from the code alone?"

Read `references/decisions-template.md` for the exact format. Follow it precisely.

Seed this with decisions already captured in AGENTS.md's Decisions section and any significant choices documented in BUILD_PLAN.md notes. Those entries move here; AGENTS.md's Decisions section is replaced with a pointer to DECISIONS.md.

### Verifying all outputs

After writing all artifacts, run the output quality eval against the project directory:

```
python ${CLAUDE_PLUGIN_ROOT}/references/eval_evolution_quality.py <project-dir>
```

Fix any FAIL findings. Present the results to the user only after the eval passes clean.

### Verifying conversation compliance

After the session, the conversation transcript can be evaluated for skill compliance:

```
python ${CLAUDE_PLUGIN_ROOT}/references/eval_skill_compliance.py <transcript.json>
```

This checks 12 behavioral rules: artifacts read before assessment, maturity signals enumerated, not-ready gate honored, health check performed, one question at a time, no numbered question lists, all three direction questions asked, assessment before restructuring, direction before generation, templates read, confirmation after artifacts, and coherence verification. Use `--format json` for structured output.

## Phase 4: Migration

### 4.1 Archive the build plan

Do not delete BUILD_PLAN.md. Rename it to `BUILD_PLAN.archived.md`. It is a useful historical record. Add a note at the top:

```markdown
# Build Plan (Archived)

This project has graduated to ROADMAP.md for ongoing work management.
This file is preserved as a historical record of the initial build sequence.
```

### 4.2 Create new files

In the project root:
1. `ROADMAP.md` (from 3.1)
2. Updated `AGENTS.md` (from 3.2)
3. `CLAUDE.md` (from 3.2 -- contains only `@agents.md`)
4. `ARCHITECTURE.md` (from 3.3)
5. `DECISIONS.md` (from 3.4)

### 4.3 Verify coherence

Check that:
- AGENTS.md's module guide covers everything in ARCHITECTURE.md's component map
- All decisions from AGENTS.md and BUILD_PLAN.md notes are captured in DECISIONS.md
- AGENTS.md's work protocol references ROADMAP.md, not BUILD_PLAN.md
- CLAUDE.md contains only `@agents.md`
- No orphaned references to BUILD_PLAN.md remain in any active document

Run the output quality eval one final time after coherence fixes:

```
python ${CLAUDE_PLUGIN_ROOT}/references/eval_evolution_quality.py <project-dir>
```

## Phase 5: Present and Confirm

Present the new artifact set to the user. Highlight:

- What changed from the old structure and why
- The initial ROADMAP contents (NOW/NEXT/LATER)
- Key decisions seeded into DECISIONS.md
- Any health issues found during assessment (tech debt, test gaps, dead code)
- How the new work protocol differs from the build loop

Ask: "Does this match where the project is? Anything wrong, missing, or in the wrong bucket?"

## The Operating Loop

The mature project loop is lighter than the build loop.

### 1. No mandatory approval per work item

The user approves the roadmap priorities, not each individual piece of work. When an item is done, present it and move on unless the user wants changes.

### 2. Test-gated work

Every work item follows a strict test bracket:

**Before starting:** Run the project's full test suite. Report the result count (e.g., "42 passed, 0 failed"). Do not start implementation if any test fails. Fix the failure first and report what broke.

**During implementation:** Write or update tests for every behavior you change or add. A feature without a test is not done. If the feature is hard to test, that is a design signal -- simplify the interface until it is testable.

**After implementation:** Run the full test suite again. Report the result count. If any test fails (including pre-existing tests), fix it before updating ROADMAP.md or presenting the work as complete.

State the test results explicitly in the conversation. "Tests pass" is not enough. "47 passed, 0 failed" is.

### 3. Coherence over correctness

The primary risk at maturity is not "built the wrong thing." The risks are "broke something that was working" and "introduced inconsistency." The test bracket catches regressions. Beyond that, review the Touches list and check conventions.

### 4. Continuous artifact maintenance

Update AGENTS.md, ARCHITECTURE.md, and DECISIONS.md as part of completing work, not as a separate activity.

### 5. Regular roadmap grooming

After completing 2-3 NOW items, review the roadmap:
- Is NOW still the right set of priorities?
- Should anything move between buckets?
- Has new information made a LATER item urgent, or a NEXT item irrelevant?
- Are there items that should be parked?

### 6. Architecture-first for significant changes

Before starting a NOW item that adds a new component, changes data flow, or introduces a new integration, update ARCHITECTURE.md with the planned change first. If it does not fit cleanly, that is a signal to reconsider the approach.

### 7. Decision logging as a forcing function

When a choice has alternatives worth 5 minutes of thought, write the DECISIONS.md entry before implementing. The act of writing "Alternatives considered" and "Consequences" often reveals the better option.

## When to Run This Again

Re-run the maturity assessment (Phase 1) when:

- The product pivots or the core interaction changes significantly
- The codebase undergoes a major refactor or migration
- A new team member joins and the artifacts feel stale
- ROADMAP.md has more than 10 items in Later and feels like a dumping ground

The artifacts should never be more than one work session out of date.

## Interaction Style

- This is a working session, not a discovery conversation. The user knows their product. Keep questions targeted.
- Be direct about health issues. Quantify: N files with inconsistent patterns, M modules with no tests, K deprecated dependencies.
- Do not over-ceremony the migration. The goal is a clean set of artifacts that match how the product actually works.
- If the user has strong opinions about bucket placement, defer to them. Push back only if something is clearly miscategorized (e.g., a critical security fix in LATER).
- If the user wants to skip or collapse artifacts (e.g., fold ARCHITECTURE.md into AGENTS.md because the codebase is not that big yet), that is fine. The artifact set scales with the product.
