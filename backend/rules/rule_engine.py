"""

Gmail Genie rule engine orchestrator.



Flow:

  1. Security + Spam (first match — safety)

  2. Entity specials (high-confidence sender shortcuts)

  3. Weighted score comparison across ALL major categories (not first-match)

  4. Fallback



Set RULE_TRACE=1 for per-email score debug output.

"""



from __future__ import annotations



from typing import Callable, List, Optional, Tuple



from backend.rules.entity_special_rules import classify_entity_special

from backend.rules.fallback_rules import classify_fallback

from backend.rules.result_builder import EmailContext, prepare_email_context

from backend.rules.rule_trace import RuleTrace, trace_enabled

from backend.rules.scored_rules import classify_scored_rules

from backend.rules.security_rules import classify_security

from backend.rules.spam_rules import classify_spam



RuleCallable = Callable[[EmailContext], Optional[dict]]



# Safety stages only — category competition happens in scored_rules.

SAFETY_PIPELINE: List[Tuple[str, RuleCallable]] = [

    ("security", classify_security),

    ("spam", classify_spam),

]



ENTITY_SHORT_CIRCUIT_CONFIDENCE = 0.93





def classify_by_rules(

    sender: str,

    subject: str,

    body_snippet: str = "",

    *,

    trace: bool = False,

) -> dict:

    ctx = prepare_email_context(

        sender=sender,

        subject=subject,

        body_snippet=body_snippet,

    )



    tracer: Optional[RuleTrace] = None

    if trace_enabled(trace):

        tracer = RuleTrace(sender=sender, subject=subject)



    for stage_name, classifier in SAFETY_PIPELINE:

        result = classifier(ctx)

        if tracer:

            tracer.record_stage(stage_name, result)

        if result is not None:

            if tracer:

                tracer.set_final(result)

                tracer.emit()

            return result



    entity = classify_entity_special(ctx)

    if tracer:

        tracer.record_stage("entity_special", entity)



    if (

        entity is not None

        and float(entity.get("confidence", 0)) >= ENTITY_SHORT_CIRCUIT_CONFIDENCE

    ):

        if tracer:

            tracer.set_final(entity)

            tracer.emit()

        return entity



    scored = classify_scored_rules(ctx, trace=tracer)

    if tracer:

        tracer.record_stage("scored_orchestrator", scored)



    if scored is not None:

        if tracer:

            tracer.set_final(scored)

            tracer.emit()

        return scored



    if entity is not None:

        if tracer:

            tracer.set_final(entity)

            tracer.emit()

        return entity



    fallback = classify_fallback(ctx)

    if tracer:

        tracer.record_stage("fallback", fallback)

        tracer.set_final(fallback)

        tracer.emit()

    return fallback


