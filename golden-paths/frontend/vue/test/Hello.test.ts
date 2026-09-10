// Contract self-test (Vue3). Mounts the demo component + the App shell via @vue/test-utils — proves
// vitest, the vue plugin, jsdom and @vue/test-utils all run end to end.
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import Hello from '../src/Hello.vue';
import App from '../src/App.vue';

describe('Hello', () => {
  it('renders the demo greeting', () => {
    expect(mount(Hello).text()).toContain('hello, weyland');
  });

  it('passes props', () => {
    expect(mount(Hello, { props: { name: 'mother' } }).text()).toContain('hello, mother');
  });

  it('App mounts the demo component', () => {
    expect(mount(App).text()).toContain('hello, weyland');
  });
});
