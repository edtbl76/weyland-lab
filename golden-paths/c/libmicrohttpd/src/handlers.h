#ifndef GOLDEN_HANDLERS_H
#define GOLDEN_HANDLERS_H

/* Pure response-builders — the contract's payloads, factored out so they are unit-testable without the
 * HTTP layer. The smoke curls the real libmicrohttpd server end-to-end. */
extern const char *golden_service;

const char *golden_health_json(void);
const char *golden_ready_json(void);
const char *golden_hello_json(void);
const char *golden_metrics_text(void);

#endif /* GOLDEN_HANDLERS_H */
