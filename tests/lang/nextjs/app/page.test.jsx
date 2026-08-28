// Proves the Next.js lane runs: next/jest's SWC transform, JSX, jsdom, testing-library and React.
import { render, screen } from "@testing-library/react";
import Page from "./page.jsx";

test("nextjs lane renders an App Router page", () => {
  render(<Page />);
  expect(screen.getByRole("heading")).toHaveTextContent("hello, weyland");
});

test("nextjs lane passes props", () => {
  render(<Page name="mother" />);
  expect(screen.getByRole("heading")).toHaveTextContent("hello, mother");
});
