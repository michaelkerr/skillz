---
name: product-discovery
description: Walk through a structured product discovery conversation before writing any code, then produce a sequenced build plan and initial CLAUDE.md context file. Use this skill whenever someone wants to start a new product, app, tool, or prototype from scratch, or says things like "I want to build...", "let's start a new project", "help me plan an app", "new product idea", or "I have an idea for...". Also trigger when someone has described what they want to build and is about to jump straight into code -- redirect them through this process first. Do NOT use for adding features to an existing codebase or for non-software projects.
---

# Product Discovery

Before any code gets written, run a structured conversation that forces clarity on what matters. The output is three artifacts: a sequenced build plan, an initial CLAUDE.md context file, and a README. No code until all three exist and the user confirms.

## Why this exists

The most common failure mode when building with AI is jumping straight to code. This produces a ball of code with no structure, and the time spent unwinding it exceeds the time saved. A 20-minute conversation before building saves hours of rework.

## Phase 1: Product Discovery Conversation

This is a conversation, not a form. Ask one question at a time. Wait for the answer. Follow up when an answer is incomplete against the section's completion test, contradicts an earlier answer, or names a constraint that affects platform, stack, data source, or user count. The goal is to understand the product well enough to sequence the build correctly.

### 1.1 The Core

Start here. Do not move to 1.2 until you can fill all three blanks: **[Who]** has **[problem: a specific action or situation, stated with frequency or consequence]** and currently **[workaround, or "nothing -- triggered by X"]**.

Ask: **"What are you building, and what problem does it solve?"**

- If they describe a solution without a problem ("I want to build a dashboard"): ask what problem it solves and for whom.
- If they name a population instead of a role or person ("busy professionals," "people who..."): ask who specifically, by role or context.
- If the problem uses category words without instances ("be more productive," "streamline workflows," "better communication"): ask for one concrete example of the problem happening. "Tell me about the last time this bit you. What happened?"
- If they name a problem but no current workaround: ask "How do you handle this today?" If the answer is "I don't," ask what triggered the need now.
- **Completion test**: A problem statement is complete when it names a concrete action or situation, a frequency or consequence, and implies a user context. "I waste 30 minutes a day copy-pasting data between Sheets and Slack" passes. "Help people be more productive" does not -- it contains a category word ("productive") without an instance of the problem.

Confirm: "So the core idea is [one sentence with who, what problem, and current state]. Right?"

### 1.2 The User

Ask: **"Who specifically will use this, and what's their context when they reach for it?"**

The answer is complete when you know three things:

1. **Who**: A role, a named person, or "me." Test: can you describe what is on their screen or desk when they reach for this tool? "Marketing managers at B2B SaaS companies with 50-200 employees" passes. "Marketers" does not -- it names a category without a context. "Me, right now" passes.
   - If they give a broad label ("busy professionals," "small businesses"): "Pick one specific person who'd use this. What's their job? What are they doing right before they need it?"

2. **Trigger moment**: What just happened that makes them reach for the tool. This determines the product's entry point.
   - If they can't name a trigger: propose two or three candidates based on the problem from 1.1. Ask which is closest.

3. **Current workaround**: How they handle the problem today.
   - If a workaround exists: the product must beat it on at least one measurable dimension -- time (2x+ faster), error rate (eliminates a class of mistakes), or capability (makes something possible that was not). Ask which dimension and by roughly how much.
   - If no workaround exists: this is a risk signal, not a dealbreaker. Ask: "If nobody is solving this today, what created the urgency now?" State the risk to the user: "No existing workaround can mean untapped opportunity or a problem that isn't painful enough to act on. Worth noting as we scope this."

### 1.3 The Core Interaction

This section defines what the product IS. Ask: **"Walk me through the single most important thing a user does in this product. Step by step."**

The answer is complete when you know four things:

1. **The one interaction**: The single behavior that makes the product worth using. Everything else is secondary.
   - If they describe more than one equally important interaction: "If you could only ship one of these, which one makes the product worth using?"
   - If they still can't choose: "Which one, on its own, would make someone switch from their current workaround?" If still stuck, propose the one closest to the core problem from 1.1 and ask if that's right.

2. **Input**: What the user brings to the interaction -- a file, typed text, a selection, pasted data, a spoken command. Name the specific artifact.
   - If they say "information" or "data" without a format: "What exactly do they type, upload, select, or paste?"

3. **Output**: What the user gets back -- a generated document, a visualization, a decision, a notification, a transformed dataset. Name the specific artifact.
   - If they say "results" or "insights" without a form: "What appears on screen when it works? Describe one specific example."

4. **Where the hard part is**: Categorize as input complexity (hard to collect, structure, or validate), processing complexity (hard to compute, transform, or decide), or output complexity (hard to present, format, or act on). This determines where the build effort concentrates in Phase 2. State your assessment to the user: "The hard part here looks like [X]. Does that match your sense?"

### 1.4 What "Done" Looks Like

Ask: **"What would you need to see in a working prototype to know this idea works?"**

**Test for testability**: A success criterion is testable if it can be written as: "Given [input/scenario], the prototype [does specific thing] in [measurable bound]."
- Testable: "I can paste a CSV and get a formatted report in under 2 minutes."
- Testable: "Given three overlapping calendar invites, it identifies the conflict and suggests a resolution."
- Not yet testable: "It feels intuitive." Ask: "What would you see or do that tells you it's intuitive? Describe the moment where you'd know."
- Not yet testable: "It works well." Ask: "Compared to what? What's the minimum bar?"

After getting their criteria:
- **Check alignment**: Does the success criterion exercise the core interaction from 1.3? If they described a report-generation tool but their success criterion is about user onboarding, name the mismatch: "Your core interaction is [X] but your success criterion tests [Y]. Which one is the real priority for the prototype?"
- **Check scope**: If they list more than 3 features as essential for the prototype, stop and ask them to rank. The prototype proves the core interaction works. Items ranked 4+ are later steps, not prototype gates.

### 1.5 Constraints and Context

Ask: **"Are there hard constraints I should know about?"**

Probe specifically for:
- **Platform**: Web, mobile, desktop, CLI, extension?
- **Tech preferences**: Do they have strong opinions on stack? Are they building on an existing codebase?
- **Data**: Where does the data come from? Is there an API? A file? User input? Does it need to persist?
- **Users**: Just them? Their team? Public? This changes everything about auth, hosting, and error handling.
- **Timeline**: Are they exploring an idea or shipping something? This affects Phase 2 scope:
  - **Exploring**: Cap at 5-7 steps. Focus on the core interaction and one or two supporting behaviors. Skip infrastructure entirely.
  - **Shipping**: Include infrastructure steps (auth, deployment, error handling, data persistence) after the core interaction is validated. 8-12 steps is typical.

### 1.6 Synthesis and Confirmation

Before moving to the build plan, summarize what you've learned:

```
## Product Summary

**Problem**: [one sentence]
**User**: [who, in what context]
**Core interaction**: [the one thing that IS the product]
**Success criteria**: [how we'll know the prototype works]
**Constraints**: [platform, stack, data, users, timeline]
```

Confirm with the user. If anything is wrong or missing, fix it before proceeding.

## Phase 2: Build Plan

Create a sequenced list of build steps. Each step produces something the user can run and evaluate.

### Sequencing principles

1. **Core interaction first.** The first build step should produce a version of the core interaction from 1.3 that the user can operate from input to output, even if unstyled and without edge-case handling. Not scaffolding, not auth, not navigation. The thing that makes the product the product. If the core interaction requires a specific data source (e.g., an API), add a separate Step 0 for data source connection so it can be evaluated independently.

2. **Each step is independently evaluable.** The user should be able to run the output of each step and say "this works" or "this is wrong" without needing the next step to exist.

3. **Each step builds on the prior working state.** Never ask AI to generate a step that requires modifying the output of a previous step in a way the user hasn't validated yet.

4. **Defer infrastructure.** Auth, deployment, CI, database setup -- these come after the core experience works.

5. **One behavior per step.** Each step describes a single user-visible behavior change. Test: if the "What it does" field contains the word "and" joining two user-visible behaviors, split it into two steps. "Add filtering to the list" is one step. "Add filtering, sorting, and pagination" is three.

6. **More granularity where the hard part is.** The complexity area identified in 1.3 (input, processing, or output) gets finer-grained steps. If the hard part is input validation, break input handling into multiple steps rather than one. If the hard part is output presentation, break the display into multiple steps.

### Generating the build plan

Read `references/build-plan-template.md` for the exact format. Follow it precisely. After writing BUILD_PLAN.md, run the output quality eval:

```
python ${CLAUDE_PLUGIN_ROOT}/references/eval_output_quality.py <project-dir>
```

Fix any FAIL findings before presenting to the user.

### The Test field

For steps whose output is deterministic (data transformations, API responses, calculations, business logic), write an assertion that specifies a literal input and a literal expected output: "Given input X, output should be Y" or "Submitting the form with email='bad' shows 'Email is required.'" Write the test before building the step. Build until it passes.

For steps whose evaluation requires human judgment (layout, interaction feel, visual design, flow), set the Test field to "manual." The user's evaluation is the test. When writing a regression test after the user approves a manual step, test structural invariants (element exists, route loads, data renders in the expected container) rather than the subjective quality that required human judgment.

A test must define expected behavior independent of implementation. "The function returns an array" is an implementation test -- it describes how the code works, not what the user sees. "Given these 3 transactions, the total displays as $47.50" is a behavior test -- it can be verified without reading the source.

Typical projects have 5-12 steps. If you have more than 15, the scope is too big for a prototype. Say so and work with the user to cut scope.

Steps can be added, removed, reordered, or split during the build. The plan is a coordination tool, not a contract.

## Phase 3: Initial Context File

Generate a CLAUDE.md file based on the discovery conversation. At project start, this file is short. It grows as the project grows.

Read `references/claude-md-template.md` for the exact format. Follow it precisely.

### What NOT to include
- Product strategy, user personas, market analysis (these don't change AI behavior)
- Rationale paragraphs (keep entries to 1-2 lines)
- Anything speculative ("we might later want to...")

## Phase 3b: README.md

The README is the human-facing document. It contains what CLAUDE.md deliberately excludes: rationale, product context, and setup instructions.

Read `references/readme-template.md` for the exact format. Follow it precisely.

When a step's "What it does" cannot be stated in one sentence, or its "What good looks like" requires more than one input/output example to cover the cases, write a brief in `/docs/{feature-name}.md` instead. This should be rare. A one-pager, not a PRD.

### Verifying all outputs

After writing all three files, run the output quality eval against the project directory:

```
python ${CLAUDE_PLUGIN_ROOT}/references/eval_output_quality.py <project-dir>
```

Fix any FAIL findings. Present the results to the user only after the eval passes clean.

## Phase 4: Hand Off and Build Loop

### Handoff

Save three files to the project root:
1. `CLAUDE.md` (from Phase 3)
2. `BUILD_PLAN.md` (from Phase 2)
3. `README.md` (from Phase 3b)

Tell the user: these are starting points. The build plan will evolve as you build. The CLAUDE.md will grow with every step. README.md gets updated when setup steps change or product decisions are made. Ready to start Step 1?

### The build loop

Once the user confirms, the ongoing workflow is:

1. **Run regression tests.** Before building anything new, run all existing tests. If anything is broken (from prior work or environment changes), fix it first.
2. **Read BUILD_PLAN.md.** Find the next step with status "not started." Set it to "in progress."
3. **Write the test first (if applicable).** If the step's Test field has a specific assertion (not "manual"), write a failing test that encodes it before writing any implementation.
4. **Build the step.** Implement only the behavior described in the step's "What it does" field. Do not add error handling, styling, or secondary behaviors unless the step names them. For steps with a test, build until it passes. For "manual" steps, build until the behavior matches "what good looks like."
5. **Present for evaluation.** Tell the user what you built, what tests pass, and how to run/evaluate it. Wait for their response.
6. **Iterate or advance.**
   - If the user identifies problems: fix them, present again.
   - If the user approves: mark the step "complete" in BUILD_PLAN.md. Fill in the Notes field with: patterns established, unexpected complexity encountered, or scope changes made. For "manual" steps that don't already have a test, write a regression test for the approved behavior so later steps don't break it (test structural invariants, not subjective quality). Update CLAUDE.md if new conventions or structural decisions emerged.
7. **Check the plan.** Before starting the next step, verify two things: (a) the next step's "Builds on" dependency is satisfied by the current state, and (b) no information from the completed step invalidates a future step's assumptions. If either check fails, update BUILD_PLAN.md and confirm the changes with the user.
8. **Repeat from 1.**

### What triggers a CLAUDE.md update

Not every step produces a CLAUDE.md change. Update it when:
- A new file/folder pattern is established (first component, first API route, first test file)
- The same library, pattern, or structural choice is used across two or more steps ("we're using fetch, not axios" -- write it down so it stays consistent)
- A structural decision is made ("state lives in URL params, not React state")
- A library, API, or approach is abandoned mid-step due to an incompatibility or limitation -- record the specific failure so it is not re-attempted

Do not update CLAUDE.md with progress tracking, status, or session notes. That's what BUILD_PLAN.md is for.

### New sessions

When the user starts a new conversation about this project, read CLAUDE.md and BUILD_PLAN.md first. Pick up from the last incomplete step. Do not ask the user to re-explain the project.

## Interaction Style

- Ask one question at a time. Do not present all questions as a list.
- **Detecting insufficient answers**: Push back when an answer exhibits any of these patterns:
  - **Category words without instances**: "all kinds of users," "various data sources," "different platforms." Name the gap: "You said 'all kinds of users' -- pick one specific person and describe their context."
  - **Quality words without measures**: "fast," "easy," "intuitive," "clean," "simple." Ask for the referent: "What would you see or measure that tells you it's fast? What's the bar?"
  - **Deferred specifics**: "it depends," "probably," "maybe some kind of," "something like." Pin it down: "Let's pick one concrete case. In that case, what happens?"
- **Adapting pace**: When the user's prior responses already fill the completion template for the current section before you ask the question, skip that section. State the extracted answer ("From what you've said, [filled template]. Correct?") and move to the next unfilled section. Do not skip sections because the user uses technical vocabulary or appears experienced. Skip only when the required information is already present in what they have said.
- **Slowing down**: When a response to a completion template contains explicit uncertainty ("I'm not sure," "maybe," "I haven't decided"), leaves an element blank, or contradicts a prior answer, that section is unresolved. For unresolved sections in 1.1-1.3: ask one follow-up that names the specific gap or contradiction, and offer one concrete example of a filled template from a comparable product to anchor the conversation. Do not advance to 1.4 until 1.1-1.3 templates are filled without contradictions. Brevity is not uncertainty. A short answer that fills the template is sufficient.
- If the user tries to skip to code ("just build me a React app that does X"), redirect: "Five minutes of clarity now saves hours of rework. What problem does this solve?" If they insist after the redirect, respect it. Produce the build plan and context file from whatever information you have. Fill gaps with stated assumptions marked **[ASSUMED]** that the user can correct during the build.
