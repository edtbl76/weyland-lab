// Expo entry — registers the root component for native + web. `expo export`/`expo start` load this
// (package.json "main"). Not exercised by the jest lane (tests render components directly).
import { registerRootComponent } from 'expo';
import App from './App';

registerRootComponent(App);
