---
name: Feature request
about: Suggest a capability or an improvement
title: ""
labels: enhancement
assignees: ""
---

## The problem

What are you trying to do that Span does not currently support? Describe the
workflow, not only the proposed API.

## Why the current behavior is insufficient

What happens today, and why it blocks the workflow.

## Proposed direction

If you have one. Keep it separate from the problem statement.

## Scope check

Span deliberately owns semantic state, evidence, freshness, and retrieval. It
does not call models, edit target repositories, run tests, or originate
authority. Requests that move those boundaries need a contract discussion
first.
