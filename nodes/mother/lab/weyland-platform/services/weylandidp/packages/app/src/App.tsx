import { createApp } from '@backstage/frontend-defaults';
import catalogPlugin from '@backstage/plugin-catalog/alpha';
import catalogGraphPlugin from '@backstage/plugin-catalog-graph/alpha';
import scaffolderPlugin from '@backstage/plugin-scaffolder/alpha';
import { navModule } from './modules/nav';

export default createApp({
  features: [catalogPlugin, catalogGraphPlugin, scaffolderPlugin, navModule],
});
