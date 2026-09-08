// The demo component the page renders and the lane tests. One template literal (not `hello, {name}`)
// so the SSR HTML carries the greeting contiguously for the smoke grep.
export function Hello({ name = 'weyland' }: { name?: string }) {
  return <h1>{`hello, ${name}`}</h1>;
}
