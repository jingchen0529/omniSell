export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuth()

  if (!auth.token.value) {
    return navigateTo("/auth/login")
  }

  if (!auth.user.value) {
    const currentUser = await auth.restoreSession()
    if (!currentUser) {
      return navigateTo("/auth/login")
    }
  }
})
