// selfcheck: the golden-path node lane must SURFACE this failure (exit non-zero). Run only via
// `--self-check` (npm run test:selfcheck); the normal run ignores /selfcheck/.
import { render, screen } from '@testing-library/react';
import { Hello } from '../app/components/Hello';

test('deliberate failure — the runner must propagate it', () => {
  render(<Hello />);
  expect(screen.getByRole('heading')).toHaveTextContent('this will not match');
});
