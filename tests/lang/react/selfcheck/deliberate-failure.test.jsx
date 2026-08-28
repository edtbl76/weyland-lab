// Run ONLY by `run-lang-tests.sh react --self-check`. MUST fail — that is the point.
// Normal runs exclude this directory via jest's testPathIgnorePatterns.
import { render, screen } from "@testing-library/react";
import { Hello } from "../Hello.jsx";

test("deliberate failure (proves the react lane can fail)", () => {
  render(<Hello />);
  expect(screen.getByRole("heading")).toHaveTextContent("this will not match");
});
