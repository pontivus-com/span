# Method grounding and evidence

**Status: supporting evidence.** This document does not add a requirement and
does not bind behaviour. It records why Span's *method* has precedent — not why
any recorded understanding is correct. The mechanism it grounds is support
currency: a conclusion is shown as current only while the source it cites still
matches. Nothing here establishes that an interpretation is true.

It is not a literature review for its own sake. It answers three questions a
reader is entitled to ask about a tool that claims to keep understanding true:

1. **Has anyone established this method?** — prior art.
2. **Is the mechanism sound and validated?** — method soundness.
3. **Can I trust the tool's claims?** — credibility.

The sections below answer all three, and state plainly what is *not* claimed.

## 1. The claim

Span does not invent a new way of tracking whether a documented statement still
rests on current source. It applies, to agent-retained code understanding,
mechanisms that are standard in requirements engineering, architecture
description, and program comprehension: layered scope, explicit traceability
from a statement to its source, change impact through those links, and a status
computed from the links rather than asserted.

Span's central guarantee — *a conclusion is shown as current only while the code
it cites still matches* — is therefore not a design opinion. It is the same
mechanism regulated industries use to decide whether a requirement is still
satisfied. That grounds the mechanism. It does not certify the interpretation,
and it cannot see a dependency nobody recorded.

## 2. Each guarantee and its grounding

| Span guarantee | Mechanism | Independent grounding |
|---|---|---|
| Every conclusion is bound to exact evidence (F1, L6) | Requirement traceability: links from an artifact to its source and to its verification | ISO/IEC/IEEE 29148:2018; IEEE 24765 vocabulary; Gotel & Finkelstein 1994; INCOSE SEBoK |
| Change invalidates only what depends on it (F2, F4, L10) | Change impact analysis through trace links | SEBoK, *System Requirements Definition*; Mäder & Egyed 2015; Rempel & Mäder 2016 |
| Status is reported at the scope being asked about (F9, L9) | Requirements at levels within a hierarchy; hierarchical abstractions | ISO 29148 (requirement levels); INCOSE SEBoK (requirement tree, allocation); C4 model (system → container → component → code) |
| Domain and semantic boundaries are legitimate scopes (Goals §2) | Bounded contexts; explicit boundaries around a model | Evans, *Domain-Driven Design* (2003); Fowler, *Bounded Context* (2014) |
| Semantic understanding is more than parsing code (Goals §2) | The concept assignment problem; program comprehension as a field | Biggerstaff, Mitbander & Webster 1993/1994; Letovsky 1987; Storey 2005 |
| Documentation drifts, and the drift is the problem (Goals §1) | Empirical study of documentation practice; a dedicated line of research on documentation drift | Aghajani et al., ICSE 2020; *A Review on Detecting and Managing Documentation Drift in Software Development*, 2025 |
| Reuse must beat re-derivation (F8, G5) | The measured cost of program comprehension; measured benefit of traceability during maintenance | Storey 2005; Mäder & Egyed 2015 |

### What the evidence actually says

- **Traceability is not ceremonial.** In a controlled study with 71 subjects,
  developers completed change tasks **24% faster and 50% more correct** with
  traceability support than without it (Mäder & Egyed 2015).
- **Completeness of traceability correlates with fewer defects.** Analysis of 24
  medium and large open-source projects found a statistically significant
  relationship between traceability completeness and lower defect rates
  (Rempel & Mäder 2016).
- **Traceability is mandatory where being wrong is expensive.** It is prescribed
  by safety-critical standards including DO-178C, ISO 26262, and IEC 61508.
- **The problem Span targets is recognised.** Documentation drift is the subject
  of current review work (2025), and practitioners report documentation problems
  as a first-order concern (Aghajani et al. 2020).
- **Understanding code is a distinct problem from reading it.** The concept
  assignment problem (Biggerstaff et al. 1993) exists precisely because mapping
  domain meaning onto code is not solved by parsing syntax.

## 3. What Span adds

The grounding above supports the *mechanisms*. It does not contain Span. The
synthesis is:

- understanding is **authored by an agent** and retained across sessions;
- every conclusion is **bound to source identity**, so currency is **computed**
  on every read rather than asserted once;
- status is **surface-scoped at variable granularity**, so a domain can honestly
  report both current and stale understanding in the same answer;
- invalidation is followed by **enumerated re-establishment**, so the change
  itself drives the repair;
- all of it is delivered to agents as an MCP contract of **five operation families**.

That combination is the contribution. The soundness of its mechanisms is
borrowed from established practice, which is exactly what makes the contribution
credible rather than speculative.

## 4. What is not claimed

- **No controlled evaluation of Span itself.** The studies above measure
  requirements traceability and documentation practice, not this tool. They
  support the mechanism; they do not measure Span's effect.
- **"Pyramid" is a presentation, not a named standard.** The established model
  is a layered requirements hierarchy with requirement trees and allocation
  (ISO 29148, INCOSE). Span presents it as a pyramid; it does not claim a
  canonical standard by that name.
- **The studies are not about AI agents.** Applying traceability to
  agent-retained understanding is the new step, and it is the step that must be
  evaluated on its own terms.
- **No claim that citation proves the product.** A design that cites good
  practice can still be implemented badly. The grounding raises the floor; it
  does not replace tests, measurement, or review.

## 5. Why this gives credibility

Every one of Span's central mechanisms maps to a body of work with independent
evidence, standardisation, or both. None of them rests on an analogy.

That means the remaining risk is implementation fidelity, adoption cost, and the
fitness measurement that F8 requires — not whether the method has a defensible
precedent. Those are the right things to be uncertain about, and they are
testable. The claim is about the method, not about any particular answer.

## 6. References

**Standards and bodies of knowledge**

- ISO/IEC/IEEE 29148:2018, *Systems and software engineering — Life cycle
  processes — Requirements engineering*, edition 2.
  https://www.iso.org/standard/72089.html
- IEEE Std 24765:2010, *Systems and software engineering — Vocabulary*
  (definition of traceability).
- INCOSE, *Guide to the Systems Engineering Body of Knowledge (SEBoK)*,
  "System Requirements Definition" and "Requirements Management".
  https://sebokwiki.org/wiki/System_Requirements_Definition
- DO-178C, ISO 26262, IEC 61508 — safety-critical standards that prescribe
  bidirectional traceability.

**Traceability and change impact**

- Gotel, O. C. Z. and Finkelstein, A. C. W., "An analysis of the requirements
  traceability problem", *Proceedings of IEEE International Conference on
  Requirements Engineering*, 1994. doi:10.1109/ICRE.1994.292398
- Mäder, P. and Egyed, A., "Do developers benefit from requirements traceability
  when evolving and maintaining a software system?", *Empirical Software
  Engineering* 20(2):413–441, 2015. doi:10.1007/s10664-014-9314-z
- Rempel, P. and Mäder, P., "Preventing Defects: The Impact of Requirements
  Traceability Completeness on Software Quality", *IEEE Transactions on Software
  Engineering*, 2016. doi:10.1109/TSE.2016.2622264

**Hierarchy, boundaries, and abstraction**

- Brown, S., *The C4 model for visualising software architecture*.
  https://c4model.com/
- Evans, E., *Domain-Driven Design: Tackling Complexity in the Heart of
  Software*, Addison-Wesley, 2003.
- Fowler, M., "Bounded Context", 2014.
  https://martinfowler.com/bliki/BoundedContext.html

**Program comprehension and semantic understanding**

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

**Documentation practice and drift**

- Aghajani, E., Nagy, C., Linares-Vásquez, M., Moreno, L., Bavota, G., Lanza, M.
  and Shepherd, D. C., *Software Documentation: The Practitioners'
  Perspective*, ICSE 2020. doi:10.1145/3377811.3380405
- *A Review on Detecting and Managing Documentation Drift in Software
  Development*, MIUCC 2025. doi:10.1109/MIUCC66482.2025.11196773
