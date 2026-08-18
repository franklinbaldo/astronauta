// @ts-check
import node from '@astrojs/node';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  vite: {
    plugins: [tailwindcss()],
    ssr: {
      // The standalone runtime is shipped inside the Python wheel, without a
      // consumer-side node_modules tree. Bundle Node dependencies into the SSR
      // output so the installed artifact is self-contained apart from Node
      // itself. Node built-ins remain external for the node SSR target.
      noExternal: true,
    },
  },
});
