// Proves the React lane runs end to end: jest, babel + JSX transform, jsdom, testing-library and
// React itself. A fixture that only called React.createElement would skip the JSX transform, which
// is the part real code depends on.
import { render, screen } from "@testing-library/react";
import { Hello } from "./Hello.jsx";

test("react lane renders a component", () => {
  render(<Hello />);
  expect(screen.getByRole("heading")).toHaveTextContent("hello, weyland");
});

test("react lane passes props", () => {
  render(<Hello name="mother" />);
  expect(screen.getByRole("heading")).toHaveTextContent("hello, mother");
});
