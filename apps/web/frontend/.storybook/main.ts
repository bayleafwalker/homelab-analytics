import { fileURLToPath } from "node:url";

import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../stories/**/*.stories.@(js|jsx|ts|tsx)"],
  addons: [
    "@storybook/addon-essentials",
    "@storybook/addon-a11y",
    "@storybook/addon-interactions",
  ],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  staticDirs: ["../public"],
  async viteFinal(viteConfig) {
    viteConfig.resolve = viteConfig.resolve || {};
    viteConfig.resolve.alias = {
      ...(viteConfig.resolve.alias || {}),
      "next/link": fileURLToPath(new URL("./next-link-mock.js", import.meta.url)),
    };
    viteConfig.esbuild = {
      ...(viteConfig.esbuild || {}),
      loader: "jsx",
      include: /.*\.[jt]sx?$/,
      exclude: [],
    };
    viteConfig.optimizeDeps = viteConfig.optimizeDeps || {};
    viteConfig.optimizeDeps.esbuildOptions = viteConfig.optimizeDeps.esbuildOptions || {};
    viteConfig.optimizeDeps.esbuildOptions.loader = {
      ...(viteConfig.optimizeDeps.esbuildOptions.loader || {}),
      ".js": "jsx",
    };
    return viteConfig;
  },
};

export default config;
