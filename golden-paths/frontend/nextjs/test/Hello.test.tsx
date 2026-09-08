// Contract self-test (Next.js). The route handlers are SSR/runtime-verified by the smoke; the jest
// lane tests the pure demo component + the shared greeting (no Next server runtime pulled into jest).
import { render, screen } from '@testing-library/react';
import { Hello } from '../components/Hello';
import { greeting, SERVICE_NAME } from '../lib/greeting';

test('renders the demo greeting', () => {
  render(<Hello />);
  expect(screen.getByRole('heading')).toHaveTextContent('hello, weyland');
});

test('passes props', () => {
  render(<Hello name="mother" />);
  expect(screen.getByRole('heading')).toHaveTextContent('hello, mother');
});

test('greeting is the known payload', () => {
  expect(greeting()).toEqual({ service: SERVICE_NAME, message: 'hello, weyland' });
});
