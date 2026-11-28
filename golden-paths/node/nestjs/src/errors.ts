// C3 structured errors: one envelope {"error": {code, message, request_id}} for every error, from a catch-all
// exception filter (Nest's idiom), and the ValidationPipe's errors as a 422 (C2). A malformed JSON body is turned
// into a 422 ApiError in bootstrap.ts, before Nest maps it to a bare 400.
import { ArgumentsHost, Catch, ExceptionFilter, HttpException, Inject, ValidationError } from '@nestjs/common';
import type { Request, Response } from 'express';
import { LOG, LogFn } from './tokens';

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly fields?: FieldError[]) {
    super(message);
  }
}

/** The ValidationPipe's exceptionFactory: class-validator errors become a 422 with per-field messages. */
export function validationFailed(errors: ValidationError[]): ApiError {
  const fields = errors.map((e) => ({ field: e.property, message: Object.values(e.constraints ?? {}).join('; ') || 'invalid' }));
  return new ApiError(422, 'validation_failed', 'the request is invalid', fields);
}

const HTTP_CODES: Record<number, string> = { 404: 'not_found', 405: 'method_not_allowed' };

@Catch()
export class EnvelopeFilter implements ExceptionFilter {
  constructor(@Inject(LOG) private readonly log: LogFn) {}

  catch(err: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const req = ctx.getRequest<Request>();
    const res = ctx.getResponse<Response>();
    const requestId = String(res.getHeader('X-Request-ID') ?? req.header('x-request-id') ?? '');
    const send = (status: number, code: string, message: string, fields?: FieldError[]) => {
      res.status(status).json({ error: { code, message, request_id: requestId, ...(fields ? { fields } : {}) } });
    };
    if (err instanceof ApiError) return send(err.status, err.code, err.message, err.fields);
    if (err instanceof HttpException) {
      const status = err.getStatus();
      if (status < 500) return send(status, HTTP_CODES[status] ?? 'http_error', err.message);
    }
    this.log(JSON.stringify({ event: 'unhandled_error', request_id: requestId, error: String((err as Error)?.stack ?? err) }));
    return send(500, 'internal', 'internal error');      // the detail goes to the log, never to the client
  }
}
