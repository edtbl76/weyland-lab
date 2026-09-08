// Browser entry — mounts <App/>. Not exercised by the jest lane (jsdom renders components directly),
// so it is excluded from coverage.
import { createRoot } from 'react-dom/client';
import { App } from './App';

createRoot(document.getElementById('root')!).render(<App />);
