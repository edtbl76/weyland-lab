// C7: the ItemStore contract, typed for TypeScript. The implementations are the shared, framework-neutral JavaScript
// (src/shared/items-store.js, a synced copy; the real backends in src/shared/items-backends.js).
export interface Item {
  id: number;
  name: string;
  tags: string[];
}

export interface ItemStore {
  open(): Promise<void>;
  close(): Promise<void>;
  create(name: string, tags: string[]): Promise<Item>;
  get(id: number): Promise<Item | null>;
  list(limit: number, offset: number): Promise<Item[]>;
}
