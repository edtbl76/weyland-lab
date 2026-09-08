// The demo component the index route renders and the lane tests.
export function Hello({ name = 'weyland' }: { name?: string }) {
  // One template literal, not `hello, {name}` — React would SSR the latter as two text nodes with a
  // `<!-- -->` marker between, so the raw-HTML smoke grep for the greeting would miss it.
  return <h1>{`hello, ${name}`}</h1>;
}
