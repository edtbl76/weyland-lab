// Contract self-test (Mobile/React Native). Renders the demo component + the App shell via
// @testing-library/react-native — proves jest-expo, the babel-preset-expo TSX transform, the RN test
// renderer, testing-library and React all run end to end in the CI node image. A mobile app has no
// HTTP surface, so this asserts the on-screen greeting (the /hello-equivalent known payload).
import { render, screen } from '@testing-library/react-native';
import { Hello, SERVICE_NAME } from '../src/Hello';
import App from '../App';

test('renders the demo greeting', () => {
  render(<Hello />);
  expect(screen.getByText('hello, weyland')).toBeTruthy();
});

test('passes props', () => {
  render(<Hello name="mother" />);
  expect(screen.getByText('hello, mother')).toBeTruthy();
});

test('App mounts the demo component', () => {
  render(<App />);
  expect(screen.getByText('hello, weyland')).toBeTruthy();
});

test('carries the service-name token', () => {
  expect(SERVICE_NAME).toBe('golden-react-native');
});
