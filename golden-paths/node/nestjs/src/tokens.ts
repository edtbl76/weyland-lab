// The injection tokens (C7): Nest providers are looked up by these, so a test or a scaffolded service swaps the
// implementation without touching a consumer.
export const ITEM_STORE = Symbol('ITEM_STORE');
export const SETTINGS = Symbol('SETTINGS');
export const LOG = Symbol('LOG');

/** One line of the JSON access / error log; console.log unless a test captures it. */
export type LogFn = (line: string) => void;
