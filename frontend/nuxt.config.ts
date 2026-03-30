import tailwindcss from "@tailwindcss/vite"

export default defineNuxtConfig({
  compatibilityDate: "2024-11-01",
  devtools: { enabled: true },
  ssr: false,
  routeRules: {},
  experimental: {
    appManifest: false,
  },
  css: ["~/assets/css/tailwind.css"],
  modules: ["shadcn-nuxt", "@nuxtjs/i18n"],
  shadcn: {
    prefix: "",
    componentDir: "./components/ui",
  },
  i18n: {
    locales: [
      { code: 'zh', name: '简体中文', file: 'zh.json' },
      { code: 'en', name: 'English', file: 'en.json' },
      { code: 'tw', name: '繁體中文', file: 'tw.json' },
      { code: 'ja', name: '日本語', file: 'ja.json' },
    ],
    defaultLocale: 'zh',
    strategy: 'no_prefix',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'omnisell-locale',
      fallbackLocale: 'zh',
    },
  },
  vite: {
    plugins: [tailwindcss()],
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://127.0.0.1:8000/api",
    },
  },
  app: {
    head: {
      title: "OmniSell AI Console",
      link: [
        { rel: "icon", type: "image/webp", href: "/favicon.webp" }
      ],
      meta: [
        {
          name: "description",
          content: "AI-assisted ecommerce operations starter built with Nuxt 3 and FastAPI.",
        },
        {
          name: "viewport",
          content: "width=device-width, initial-scale=1",
        },
      ],
    },
  },
});
