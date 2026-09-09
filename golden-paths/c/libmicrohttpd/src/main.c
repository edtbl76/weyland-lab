#include <microhttpd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "handlers.h"

static enum MHD_Result respond(struct MHD_Connection *conn, unsigned int code, const char *ctype,
                               const char *body) {
  struct MHD_Response *resp =
      MHD_create_response_from_buffer(strlen(body), (void *)body, MHD_RESPMEM_PERSISTENT);
  MHD_add_response_header(resp, "Content-Type", ctype);
  enum MHD_Result ret = MHD_queue_response(conn, code, resp);
  MHD_destroy_response(resp);
  return ret;
}

static enum MHD_Result handle_request(void *cls, struct MHD_Connection *conn, const char *url,
                                      const char *method, const char *version,
                                      const char *upload_data, size_t *upload_data_size,
                                      void **req_cls) {
  (void)cls;
  (void)version;
  (void)upload_data;
  (void)upload_data_size;
  (void)req_cls;

  if (strcmp(method, "GET") != 0) return respond(conn, 405, "text/plain", "method not allowed");
  if (strcmp(url, "/health") == 0) return respond(conn, 200, "application/json", golden_health_json());
  if (strcmp(url, "/ready") == 0) return respond(conn, 200, "application/json", golden_ready_json());
  if (strcmp(url, "/hello") == 0) return respond(conn, 200, "application/json", golden_hello_json());
  if (strcmp(url, "/metrics") == 0)
    return respond(conn, 200, "text/plain; version=0.0.4", golden_metrics_text());
  return respond(conn, 404, "text/plain", "not found");
}

int main(void) {
  const char *port_env = getenv("PORT");
  unsigned short port = port_env ? (unsigned short)atoi(port_env) : 8080;

  struct MHD_Daemon *daemon = MHD_start_daemon(MHD_USE_INTERNAL_POLLING_THREAD, port, NULL, NULL,
                                               &handle_request, NULL, MHD_OPTION_END);
  if (daemon == NULL) {
    fprintf(stderr, "failed to start MHD daemon on port %u\n", port);
    return 1;
  }
  for (;;) pause(); /* run until the container is torn down */
  return 0;
}
