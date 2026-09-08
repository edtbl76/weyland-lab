// Golden path — Node / NestJS (B153). Runnable, ephemeral, extendable. Conforms to the golden-path
// contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
// Scaffold FROM it: scripts/new-service.sh node/nestjs <your-service>.
import { Controller, Get, Header } from '@nestjs/common';
import * as client from 'prom-client';

export const SERVICE_NAME = 'golden-node-nestjs';

const helloHits = new client.Counter({
  name: 'golden_hello_requests_total',
  help: 'Calls to the demo /hello endpoint',
});

@Controller()
export class AppController {
  @Get('/health')
  health() {
    return { status: 'ok' };
  }

  @Get('/ready')
  ready() {
    return { status: 'ready' };
  }

  @Get('/hello')
  hello() {
    helloHits.inc();
    return { service: SERVICE_NAME, message: 'hello, weyland' };
  }

  @Get('/metrics')
  @Header('Content-Type', 'text/plain; version=0.0.4')
  metrics(): Promise<string> {
    return client.register.metrics();
  }
}
