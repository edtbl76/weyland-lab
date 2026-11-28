// C8 lifecycle: readiness and the store's open/close. start() opens the store and flips /ready (bootstrap.ts calls it
// after listen, so /ready answers 503 until it has: OnModuleInit runs before the server accepts a request and would
// leave no 503 window). OnApplicationShutdown closes the store when app.close() has drained (main.ts calls it on SIGTERM).
import { Inject, Injectable, OnApplicationShutdown } from '@nestjs/common';
import { ITEM_STORE } from './tokens';
import type { ItemStore } from './store';

@Injectable()
export class Lifecycle implements OnApplicationShutdown {
  ready = false;

  constructor(@Inject(ITEM_STORE) private readonly store: ItemStore) {}

  async start() {
    await this.store.open();
    this.ready = true;
  }

  async onApplicationShutdown() {
    this.ready = false;
    await this.store.close();
  }
}
