// GENERATED from golden-paths-shared/node/src/shared/settings.js by scripts/sync-golden-shared.sh: edit the source, not this copy.
// settings — deep contract v2 C6, framework-neutral (B262): config is read and VALIDATED once, at startup, so a bad
// value stops the service before it serves (never read lazily on a request).
//
// SOURCE: golden-paths-shared/node/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
'use strict';

const DEFAULT_GREETING = 'hello, weyland';

/** The validated settings from the environment; throws with a clear message on an invalid value. */
function loadSettings(env = process.env) {
  const greeting = env.GOLDEN_GREETING ?? DEFAULT_GREETING;
  if (!greeting.trim()) {
    throw new Error('GOLDEN_GREETING must not be empty');
  }
  return Object.freeze({ greeting });
}

module.exports = { loadSettings, DEFAULT_GREETING };
