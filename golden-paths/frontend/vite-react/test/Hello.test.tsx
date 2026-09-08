// Contract self-test (Vite+React). Renders the demo component + the App shell via testing-library —
// proves jest, the babel TSX transform, jsdom, testing-library and React all run end to end.
import { render, screen } from '@testing-library/react';
import { Hello } from '../src/Hello';
import { App } from '../src/App';

test('renders the demo greeting', () => {
  render(<Hello />);
  expect(screen.getByRole('heading')).toHaveTextContent('hello, weyland');
});

test('passes props', () => {
  render(<Hello name="mother" />);
  expect(screen.getByRole('heading')).toHaveTextContent('hello, mother');
});

test('App mounts the demo component', () => {
  render(<App />);
  expect(screen.getByRole('heading')).toHaveTextContent('hello, weyland');
});
