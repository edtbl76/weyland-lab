// Contract self-test (Remix). The resource-route loaders are SSR-verified by the smoke; the jest lane
// tests the pure demo component + the shared greeting (no Remix server runtime pulled into jest).
import { render, screen } from '@testing-library/react';
import { Hello } from '../app/components/Hello';
import { greeting, SERVICE_NAME } from '../app/lib/greeting';

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
