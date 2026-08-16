import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  base: '/',
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/health': 'http://127.0.0.1:8765',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Split vendors so the production JS can be uploaded in pieces
        // (GitHub MCP file commits are unreliable above ~80–100k).
        manualChunks(id) {
          if (id.includes('node_modules/prosemirror-view')) return 'pm-view';
          if (id.includes('node_modules/prosemirror-model')) return 'pm-model';
          if (
            id.includes('node_modules/prosemirror-tables') ||
            id.includes('node_modules/prosemirror-transform')
          ) {
            return 'pm-table';
          }
          if (id.includes('node_modules/prosemirror') || id.includes('node_modules/@tiptap/pm')) {
            return 'pm-rest';
          }
          if (id.includes('node_modules/@tiptap/core')) return 'tiptap-core';
          if (id.includes('node_modules/@tiptap')) return 'tiptap-ext';
          if (id.includes('node_modules/svelte') || id.includes('node_modules/@sveltejs')) {
            return 'svelte';
          }
          if (id.includes('node_modules')) {
            return 'vendor';
          }
        },
      },
    },
  },
  test: {
    environment: 'node',
  },
});
