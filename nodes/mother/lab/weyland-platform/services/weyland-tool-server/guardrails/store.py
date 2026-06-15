from .verdict import Verdict, Hook, Mode


def record_verdict(conn, request_id: str, hook: Hook, mode: Mode, verdict: Verdict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guardrail_verdicts
                (request_id, hook, validator, mode, decision, score, reason, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request_id,
                str(hook.value),
                verdict.validator,
                str(mode.value),
                str(verdict.decision.value),
                verdict.score,
                verdict.reason,
                verdict.latency_ms,
            ),
        )
