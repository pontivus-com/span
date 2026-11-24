# Method grounding and evidence

**Status: supporting evidence.** This document does not add product requirements
or bind Span behavior.

It answers two different credibility questions:

1. **Is the problem Span addresses visible in current agent engineering?**
2. **Do the software-maintenance mechanisms Span uses have established
   precedent?**

The first is industry/context evidence. The second is method grounding.

Neither one proves that a particular Span conclusion is semantically correct,
and neither one replaces Span's Functional Pyramid authority, implementation
tests, or real-world product validation.

## 1. Current agent-industry problem evidence

Span's public narrative starts from a problem: coding agents can gather large
amounts of context for one task, while useful understanding produced during that
work is easily lost, inconsistently reused, or allowed to drift.

That problem is not unique to Span.

### Knowledge needs to be maintained, not merely retrieved

In November 2026, LangChain's
[How to build a knowledge factory](https://www.langchain.com/blog/knowledge-factory)
argues that the missing ingredient for useful organizational agents is not only
better models or more context, but maintained knowledge.

The article distinguishes:

- **context** — what an agent has available for a task; and
- **knowledge** — reusable understanding maintained so future tasks can be done
  correctly.

It describes a **knowledge factory** as a system for collecting, curating, and
maintaining that knowledge, with agents doing real work helping reveal what is
missing or wrong.

It also argues that task agents should not be solely responsible for maintaining
the shared knowledge they consume, because their immediate objective is the task
in front of them. A separate curation function maintains the reusable knowledge.

This supports Span's public problem framing and the separation between
evidence-near capture and later review/curation.

It does **not** make LangChain's background-curator architecture a Span
requirement. Span is a narrower software-engineering knowledge layer and its
canonical behavior remains defined by Span's own Functional Pyramid.

### More context creates its own engineering problems

LangChain's 2025
[Context Engineering](https://www.langchain.com/blog/context-engineering-for-agents)
describes agent context as a limited working resource that must be written,
selected, compressed, and isolated deliberately.

It identifies problems associated with growing or poorly selected context,
including cost/latency, context distraction, context confusion, and conflicting
context.

This supports a second part of Span's framing: repeatedly reconstructing or
indiscriminately loading more raw context is not the same thing as maintaining
useful, task-relevant software knowledge.

Again, this is industry context, not Span authority.

## 2. Software-engineering method grounding

Span does not invent traceability, change-impact analysis, hierarchical scope,
or program comprehension.

It applies those established mechanisms to agent-retained software
understanding.

The key methodological idea is:

> a retained conclusion is reusable only while the dependencies recorded for it
> still satisfy their owning checks.

That grounds support currency. It does not certify the interpretation itself,
and it cannot detect a dependency the investigator failed to record.

## 3. Each mechanism and its precedent

| Span mechanism | Established practice | Independent grounding |
|---|---|---|
| Conclusions retain explicit evidence/support | Requirements traceability: links between artifacts, sources, and verification | ISO/IEC/IEEE 29148:2018; IEEE 24765; Gotel & Finkelstein 1994; INCOSE SEBoK |
| Change identifies affected dependents | Change-impact analysis through trace links | SEBoK; Mäder & Egyed 2015; Rempel & Mäder 2016 |
| Status is scoped rather than repository-global | Hierarchical requirements and architectural abstraction | ISO 29148; INCOSE SEBoK; C4 model |
| Service/domain boundaries can be semantic scopes | Explicit bounded models and contexts | Evans 2003; Fowler 2014 |
| Understanding code is more than parsing syntax | Program comprehension / concept assignment | Biggerstaff et al. 1993/1994; Letovsky 1987; Storey 2005 |
| Documentation can drift from implementation | Empirical documentation-practice and drift research | Aghajani et al. 2020; documentation-drift review 2025 |
| Reuse must justify its maintenance overhead | Program-comprehension cost and maintenance traceability evidence | Storey 2005; Mäder & Egyed 2015 |

### What the cited studies support

**Traceability can materially help maintenance work.** Mäder & Egyed (2015)
reported that, in their controlled study of 71 subjects, developers completed
change tasks faster and with higher correctness when traceability support was
available.

**Traceability completeness is associated with software quality.** Rempel &
Mäder (2016) reported a statistically significant relationship between
traceability completeness and lower defect rates across the projects they
studied.

**Traceability is treated as a serious engineering mechanism where change
assurance matters.** It appears in established requirements-engineering bodies
of knowledge and safety-critical standards.

**Software comprehension is a distinct engineering problem.** The program-
comprehension literature treats mapping implementation structure to domain
meaning as a separate problem from parsing syntax.

**Documentation drift is a recognized maintenance problem.** Practitioner and
review literature documents the cost of documentation becoming incomplete,
incorrect, or out of sync with software.

These findings support the mechanisms Span borrows. They do not establish
Span's product effectiveness by themselves.

## 4. What Span combines

Span's contribution is the combination of established software-maintenance
mechanisms with the current knowledge-factory problem:

- useful software understanding is authored during real engineering work;
- that understanding is retained outside the originating model session;
- capture and shared-reuse review are separate acts;
- retained conclusions stay connected to declared support;
- support currency is recomputed from present dependencies rather than assumed;
- governing project guidance remains distinct from implementation evidence;
- changes identify affected retained knowledge for focused reassessment; and
- the lifecycle is delivered to coding agents through three MCP operations.

The individual mechanisms have precedent. Their composition into this
agent-facing software-knowledge lifecycle is Span's product design.

## 5. What is not claimed

- **The LangChain articles do not validate Span.** They support the current
  agent-industry problem framing and knowledge-factory category.
- **Span does not implement LangChain's entire knowledge-factory topology.**
  In particular, Span does not ship a background curator model.
- **No citation makes a Span interpretation true.** Semantic judgment remains
  with the investigator/reviewer.
- **No traceability study is a controlled evaluation of Span.** Existing studies
  ground mechanisms; they do not measure Span's effect on time, tokens, or
  correctness.
- **"Functional Pyramid" is Span's presentation, not a named industry
  standard.** Layered requirements hierarchies and allocation have independent
  precedent; Span's exact model is its own.
- **A recorded dependency set can be incomplete.** Deterministic support checks
  cannot detect an important dependency that was never recorded.
- **A sound method can be implemented badly.** Runtime behavior still requires
  tests, acceptance evidence, and real-world evaluation.

## 6. What this evidence is useful for

The industry evidence supports the statement:

> agents need maintained reusable knowledge, not only larger amounts of raw
> task context.

The engineering evidence supports the statement:

> software knowledge can be maintained more responsibly when its support,
> scope, and change effects are explicit.

The remaining product questions are empirical:

- Does Span implement those mechanisms faithfully?
- Is the workflow usable enough to justify its overhead?
- Does retained knowledge actually improve later engineering work?
- Which host and workflow combinations deliver the intended value?

Those questions belong to [Acceptance and evidence](acceptance.md) and sustained
real-world Beta use rather than to this method-grounding document.

## 7. References

### Agent knowledge and context engineering

- Chase, H., "How to build a knowledge factory for AI agents", LangChain,
  21 November 2026.
  https://www.langchain.com/blog/knowledge-factory
- LangChain Team, "Context Engineering", 2 July 2025.
  https://www.langchain.com/blog/context-engineering-for-agents

### Standards and bodies of knowledge

- ISO/IEC/IEEE 29148:2018, *Systems and software engineering — Life cycle
  processes — Requirements engineering*, edition 2.
  https://www.iso.org/standard/72089.html
- IEEE Std 24765:2010, *Systems and software engineering — Vocabulary*.
- INCOSE, *Guide to the Systems Engineering Body of Knowledge (SEBoK)*,
  "System Requirements Definition" and "Requirements Management".
  https://sebokwiki.org/wiki/System_Requirements_Definition
- DO-178C, ISO 26262, IEC 61508 — safety-critical standards that prescribe
  bidirectional traceability.

### Traceability and change impact

- Gotel, O. C. Z. and Finkelstein, A. C. W., "An analysis of the requirements
  traceability problem", *Proceedings of IEEE International Conference on
  Requirements Engineering*, 1994. doi:10.1109/ICRE.1994.292398
- Mäder, P. and Egyed, A., "Do developers benefit from requirements traceability
  when evolving and maintaining a software system?", *Empirical Software
  Engineering* 20(2):413–441, 2015. doi:10.1007/s10664-014-9314-z
- Rempel, P. and Mäder, P., "Preventing Defects: The Impact of Requirements
  Traceability Completeness on Software Quality", *IEEE Transactions on Software
  Engineering*, 2016. doi:10.1109/TSE.2016.2622264

### Hierarchy, boundaries, and abstraction

- Brown, S., *The C4 model for visualising software architecture*.
  https://c4model.com/
- Evans, E., *Domain-Driven Design: Tackling Complexity in the Heart of
  Software*, Addison-Wesley, 2003.
- Fowler, M., "Bounded Context", 2014.
  https://martinfowler.com/bliki/BoundedContext.html

### Program comprehension and semantic understanding

- Biggerstaff, T. J., Mitbander, B. G. and Webster, D., "The concept assignment
  problem in program understanding", *Working Conference on Reverse
  Engineering*, 1993. doi:10.1109/WCRE.1993.287781
- Biggerstaff, T. J., Mitbander, B. G. and Webster, D., "Program understanding
  and the concept assignment problem", *Communications of the ACM*, 1994.
  doi:10.1145/175290.175300
- Letovsky, S., "Cognitive processes in program comprehension", *Journal of
  Systems and Software* 7(4):325–339, 1987.
  doi:10.1016/0164-1212(87)90032-X
- Storey, M.-A., "Theories, methods and tools in program comprehension: Past,
  present and future", *13th International Workshop on Program Comprehension*,
  2005. doi:10.1109/WPC.2005.38

### Documentation practice and drift

- Aghajani, E., Nagy, C., Linares-Vásquez, M., Moreno, L., Bavota, G., Lanza, M.
  and Shepherd, D. C., *Software Documentation: The Practitioners'
  Perspective*, ICSE 2020. doi:10.1145/3377811.3380405
- *A Review on Detecting and Managing Documentation Drift in Software
  Development*, MIUCC 2025. doi:10.1109/MIUCC66482.2025.11196773
