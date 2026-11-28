// items-store — the deep contract v2 ItemStore, framework-neutral (B163; shared by every Node golden path, B262).
//
// An item is a plain object {id: number, name: string, tags: string[]}: each framework validates requests with its own
// idiom (zod, JSON Schema, class-validator) and hands the store already-valid values. Every method is async, so the
// in-memory store and the real ones (items-backends.js) share one interface. The in-memory store is the default, so a
// path runs with no backend.
//
// SOURCE: golden-paths-shared/node/. Each path holds a synced copy (scripts/sync-golden-shared.sh); a guard fails CI if
// a copy drifts. Edit this file, never a copy.
'use strict';

/**
 * @typedef {{ id: number, name: string, tags: string[] }} Item
 * @typedef {{
 *   open(): Promise<void>, close(): Promise<void>,
 *   create(name: string, tags: string[]): Promise<Item>,
 *   get(id: number): Promise<Item | null>,
 *   list(limit: number, offset: number): Promise<Item[]>
 * }} ItemStore
 */

/** The default store: no backend, so the template runs anywhere. */
class InMemoryItemStore {
  constructor() {
    this.items = new Map();
    this.nextId = 1;
    this.closed = false;
  }

  async open() {
    this.closed = false;
  }

  async close() {
    this.closed = true;
  }

  async create(name, tags) {
    const item = { id: this.nextId++, name, tags: [...tags] };
    this.items.set(item.id, item);
    return { ...item, tags: [...item.tags] };
  }

  async get(id) {
    const found = this.items.get(id);
    return found ? { ...found, tags: [...found.tags] } : null;
  }

  async list(limit, offset) {
    return [...this.items.keys()].sort((a, b) => a - b).slice(offset, offset + limit)
      .map((k) => ({ ...this.items.get(k), tags: [...this.items.get(k).tags] }));
  }
}

module.exports = { InMemoryItemStore };
