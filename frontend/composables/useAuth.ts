interface AuthUser {
  id: number
  email: string
  display_name: string
  created_at: string
}

interface AuthTokenResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

interface LoginPayload {
  email: string
  password: string
}

interface RegisterPayload extends LoginPayload {
  display_name: string
}

export function useAuth() {
  const tokenCookie = useCookie<string | null>("omnisell_token", {
    sameSite: "lax",
    secure: false,
  })
  const token = useState<string | null>("auth.token", () => tokenCookie.value ?? null)
  const user = useState<AuthUser | null>("auth.user", () => null)
  const api = useOmniSellApi()

  const applySession = (session: AuthTokenResponse | null) => {
    token.value = session?.access_token ?? null
    tokenCookie.value = session?.access_token ?? null
    user.value = session?.user ?? null
  }

  const clearSession = () => {
    applySession(null)
  }

  const login = async (payload: LoginPayload) => {
    const session = await api<AuthTokenResponse>("/auth/login", {
      method: "POST",
      auth: false,
      body: payload,
    })

    applySession(session)
    return session.user
  }

  const register = async (payload: RegisterPayload) => {
    const session = await api<AuthTokenResponse>("/auth/register", {
      method: "POST",
      auth: false,
      body: payload,
    })

    applySession(session)
    return session.user
  }

  const restoreSession = async () => {
    if (!token.value) {
      clearSession()
      return null
    }

    try {
      const currentUser = await api<AuthUser>("/auth/me")
      user.value = currentUser
      return currentUser
    } catch {
      clearSession()
      return null
    }
  }

  const logout = async () => {
    try {
      if (token.value) {
        await api("/auth/logout", {
          method: "POST",
        })
      }
    } catch {
      // Best effort logout; local state is cleared either way.
    } finally {
      clearSession()
    }
  }

  return {
    token,
    user,
    login,
    register,
    logout,
    restoreSession,
    clearSession,
  }
}
