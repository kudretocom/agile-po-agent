# Verified TypeSafe Jev contract

Verified on 2026-09-23 against TypeSafe's official documentation and public OpenAPI document:

- <https://docs.typesafe.ai/api.md>
- <https://docs.typesafe.ai/primitives.md>
- <https://docs.typesafe.ai/confidence.md>
- <https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md>
- <https://api.typesafe.ai/openapi.json>

The direct API contract is:

```http
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

Requests contain `model`, `state`, and a non-empty `questions` map. This project sends seven independent questions in one request. In particular, `needs_web_research` and `needs_repository_files` are separate Noul questions and are never combined.

Responses contain a resolved `model`, an `answers` map with exactly the requested question ids, and integer `usage.input_tokens` / `usage.output_tokens` counters.

## Answer validation

- Noul requires `type: "noul"` and a finite `noul` probability in `[0, 1]`. Values between `NOUL_NO_THRESHOLD` and `NOUL_YES_THRESHOLD` remain uncertain and stop automatic routing.
- Choice requires `type: "choice"`, a selected requested option, every requested option probability, a distribution summing to one within a bounded display-rounding tolerance, and confidence in `[0, 1]`.
- Score requires `type: "score"`, the exact requested legend, every rubric-level probability, a score consistent with the probability-weighted rubric after accounting for the API's rounded display probabilities, and confidence in `[0, 1]`.

Missing, extra, malformed, non-finite, out-of-range, contradictory, oversized, non-JSON, HTTP-error, and timeout responses fail closed. Upstream response bodies and credentials are not included in operator errors.

## Control boundaries

Jev supplies narrow recommendations. Python code owns thresholds, evidence acquisition, iteration limits, deterministic readiness, delivery checks, and all side effects. `ready_to_ship` is evaluated only together with tests, lint, typecheck, zero unresolved blockers, explicit human approval, and an unambiguous action recommendation. Jev never calls Jira.

The draft loop is bounded by `MAX_STEPS`. A required web or repository context signal stops the loop unless the caller separately confirms that evidence was collected. A value near `0.5` is not coerced to yes or no.

## Non-production smoke test

The smoke command sends synthetic state only and prints model, token usage, latency, and non-secret decision values:

```sh
TYPESAFE_ENVIRONMENT=non-production \
  .venv/bin/agile-po jev-smoke --confirm-non-production
```

Run it only with a credential approved for non-production use and injected through the approved secret-management flow. Never copy a production credential into the pilot. The command refuses to run without both the environment marker and explicit confirmation.
