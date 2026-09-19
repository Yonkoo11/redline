import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'
import { resolve } from 'node:path'

// Four routes, four entry points. GitHub Pages serves /policy/ from policy/index.html, so the
// paths are real directories rather than a client-side router that breaks on a hard refresh.
export default defineConfig({
  base: './',
  plugins: [svelte()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        policy: resolve(__dirname, 'policy/index.html'),
        log: resolve(__dirname, 'log/index.html'),
        guide: resolve(__dirname, 'guide/index.html'),
      },
    },
  },
})
