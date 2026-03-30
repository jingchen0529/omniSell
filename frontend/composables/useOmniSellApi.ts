export function useOmniSellApi() {
  const config = useRuntimeConfig()
  const tokenCookie = useCookie<string | null>("omnisell_token", {
    sameSite: "lax",
    secure: false,
  })

  return function <T>(
    path: string,
    options: (Parameters<typeof $fetch>[1] & { auth?: boolean }) = {},
  ) {
    const { auth = true, ...fetchOptions } = options
    const headers = new Headers(fetchOptions.headers as HeadersInit | undefined)

    if (auth && tokenCookie.value && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${tokenCookie.value}`)
    }

    return $fetch<T>(path, {
      baseURL: config.public.apiBase,
      ...fetchOptions,
      headers,
    })
  }
}
