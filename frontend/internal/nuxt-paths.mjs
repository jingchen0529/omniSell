import { joinRelativeURL } from "ufo";

const APP_DEFAULTS = {
  baseURL: process.env.NUXT_APP_BASE_URL || process.env.NITRO_APP_BASE_URL || "/",
  buildAssetsDir: process.env.NUXT_APP_BUILD_ASSETS_DIR || "/_nuxt/",
  cdnURL: process.env.NUXT_APP_CDN_URL || "",
};

export function baseURL() {
  return APP_DEFAULTS.baseURL;
}

export function buildAssetsDir() {
  return APP_DEFAULTS.buildAssetsDir;
}

export function publicAssetsURL(...path) {
  const publicBase = APP_DEFAULTS.cdnURL || APP_DEFAULTS.baseURL;
  return path.length ? joinRelativeURL(publicBase, ...path) : publicBase;
}

export function buildAssetsURL(...path) {
  return joinRelativeURL(publicAssetsURL(), buildAssetsDir(), ...path);
}
