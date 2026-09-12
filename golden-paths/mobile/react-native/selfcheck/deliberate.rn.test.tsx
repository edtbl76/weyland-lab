// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Excluded from the
// normal run (package.json "test" ignores /selfcheck/); run only via `npm run test:selfcheck`. This
// proves the runner propagates a test failure rather than swallowing it — a green selfcheck would mean
// the lane verifies nothing.
import { render, screen } from '@testing-library/react-native';
import { Hello } from '../src/Hello';

test('deliberate failure — the runner must propagate it', () => {
  render(<Hello />);
  expect(screen.getByText('this will not match')).toBeTruthy();
});
