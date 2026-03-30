import zh from './locales/zh.json'
import en from './locales/en.json'
import tw from './locales/tw.json'
import ja from './locales/ja.json'

export default defineI18nConfig(() => ({
  legacy: false,
  locale: 'zh',
  fallbackLocale: 'zh',
  messages: {
    zh,
    en,
    tw,
    ja,
  },
}))
