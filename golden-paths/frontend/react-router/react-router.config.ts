// React Router framework mode (Remix's successor). SSR on, so the demo route is server-rendered like it was on Remix.
import type { Config } from '@react-router/dev/config';

export default {
  ssr: true,
} satisfies Config;
