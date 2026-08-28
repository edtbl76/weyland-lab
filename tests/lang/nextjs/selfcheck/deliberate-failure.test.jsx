// Run ONLY by `run-lang-tests.sh nextjs --self-check`. MUST fail — that is the point.
import { render, screen } from "@testing-library/react";
import Page from "../app/page.jsx";

test("deliberate failure (proves the nextjs lane can fail)", () => {
  render(<Page />);
  expect(screen.getByRole("heading")).toHaveTextContent("this will not match");
});
