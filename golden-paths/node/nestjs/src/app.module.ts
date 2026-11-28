// C7 modules / providers. AppModule.forRoot() wires the store, the settings and the log line sink as providers; each
// is overridable (a test injects its own store, a scaffolded service the real backends). The defaults: the in-memory
// store, loadSettings() (the env, validated as the module is built: C6) and console.log.
import { DynamicModule, Module, Type } from '@nestjs/common';
import { AppController } from './app.controller';
import { ItemsController } from './items.controller';
import { Lifecycle } from './lifecycle';
import { RequestContextMiddleware } from './request-context.middleware';
import { EnvelopeFilter } from './errors';
import { ITEM_STORE, LOG, LogFn, SETTINGS } from './tokens';
import type { ItemStore } from './store';
import { InMemoryItemStore } from './shared/items-store';
import { loadSettings } from './shared/settings';

export interface AppOptions {
  store?: ItemStore;
  settings?: { greeting: string };
  log?: LogFn;
  /** More modules to import (the tests' /boom and /slow routes). */
  extraModules?: Type<unknown>[];
}

@Module({})
export class AppModule {
  static forRoot({ store, settings, log, extraModules = [] }: AppOptions = {}): DynamicModule {
    return {
      module: AppModule,
      imports: extraModules,
      controllers: [AppController, ItemsController],
      providers: [
        { provide: ITEM_STORE, useValue: store ?? new InMemoryItemStore() },
        { provide: SETTINGS, useFactory: () => settings ?? loadSettings() },
        { provide: LOG, useValue: log ?? ((line: string) => console.log(line)) },
        Lifecycle,
        EnvelopeFilter,
        RequestContextMiddleware,               // applied globally in bootstrap.ts, ahead of the body parser
      ],
    };
  }

}
