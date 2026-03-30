export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuth()

  if (!auth.token.value) {
    return
  }

  if (!auth.user.value) {
    const currentUser = await auth.restoreSession()
    if (!currentUser) {
      return
    }
  }

  return navigateTo("/")
})
