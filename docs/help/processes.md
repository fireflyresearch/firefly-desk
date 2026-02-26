---
type: tutorial
---

# Processes

The Processes section manages business process discovery and exploration. Firefly Desk uses AI to automatically identify business processes by analyzing your catalog systems, knowledge base documents, and knowledge graph entities.

## What Is a Business Process?

A business process is a sequence of steps that accomplish a business goal -- for example, "Employee Onboarding" or "Invoice Approval." Each process consists of ordered steps, where each step may reference a catalog system endpoint, and dependencies that define the execution flow between steps.

## Automatic Discovery

The Process Discovery Engine analyzes your entire enterprise context to identify processes:

1. **Context gathering** -- The engine collects all catalog systems and their endpoints, knowledge graph entities and relationships, and knowledge base documents.
2. **LLM analysis** -- This context is sent to the configured LLM with specialized Jinja2 prompts that instruct it to identify business processes, their steps, and dependencies.
3. **Structured parsing** -- The LLM returns structured JSON that is validated and converted to process models.
4. **Smart merging** -- Discovered processes are merged with existing ones. Processes you have manually verified or modified are never overwritten. Only auto-discovered processes get updated.

Discovery runs as a background job. You can trigger it manually or let it run automatically when new systems or documents are added.

## Process States

Each process has a lifecycle status:

- **Discovered** -- Automatically identified by the AI. May be updated on the next discovery run.
- **Verified** -- An admin has reviewed and confirmed the process. Protected from automatic overwrites.
- **Modified** -- An admin has edited the process details. Also protected from overwrites.
- **Archived** -- No longer active but preserved for reference.

## Process Explorer

The process explorer lets you view each process as a series of steps with their system and endpoint references. You can see inputs and outputs for each step, the dependency graph showing execution order, and confidence scores from the discovery engine. Use the explorer to review discovered processes, verify accurate ones, and edit or archive incorrect ones.

## Tips

- Verify important processes promptly -- verified processes are protected from being overwritten on the next discovery run.
- Add more catalog endpoints and knowledge documents to improve discovery accuracy.
- The confidence score (0-100%) indicates how certain the AI is about the process. Review low-confidence processes carefully.
- Processes link directly to catalog endpoints, so keeping your catalog up to date improves process quality.
