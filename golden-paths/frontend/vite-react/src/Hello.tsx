// Golden path — Frontend / Vite+React (B153). The demo component the page renders and the lane tests.
export function Hello({ name = 'weyland' }: { name?: string }) {
  return <h1>hello, {name}</h1>;
}
