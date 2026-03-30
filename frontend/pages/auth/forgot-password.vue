<script setup lang="ts">
import Button from "@/components/ui/button/Button.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import Input from "@/components/ui/input/Input.vue"

const { t } = useI18n();

definePageMeta({
  middleware: "guest",
})

interface ForgotPasswordResponse {
  message: string
  reset_token: string
  reset_url: string
}

const api = useOmniSellApi()
const router = useRouter()

const email = ref("")
const loading = ref(false)
const error = ref("")
const successMessage = ref("")
const resetToken = ref("")
const resetUrl = ref("")

const submit = async () => {
  error.value = ""
  successMessage.value = ""

  if (!email.value.trim()) {
    error.value = t('forgotPassword.errorEmailRequired')
    return
  }

  loading.value = true

  try {
    const response = await api<ForgotPasswordResponse>("/auth/forgot-password", {
      method: "POST",
      auth: false,
      body: {
        email: email.value.trim(),
      },
    })
    successMessage.value = response.message
    resetToken.value = response.reset_token
    resetUrl.value = response.reset_url
  } catch (submitError: unknown) {
    if (submitError && typeof submitError === "object") {
      const detail = (submitError as { data?: { detail?: string } }).data?.detail
      error.value = detail || t('forgotPassword.errorFailed')
    } else {
      error.value = t('forgotPassword.errorFailed')
    }
  } finally {
    loading.value = false
  }
}

const goToReset = async () => {
  if (!resetToken.value) {
    return
  }

  await router.push(`/reset-password?token=${encodeURIComponent(resetToken.value)}`)
}

useHead({
  title: computed(() => t('forgotPassword.pageTitle')),
})
</script>

<template>
  <main class="min-h-screen bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_42%,#ffffff_100%)] px-4 py-8 text-slate-900 dark:bg-[linear-gradient(180deg,#171717_0%,#1e1e1e_42%,#171717_100%)] dark:text-white">
    <div class="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center justify-center">
      <div class="grid w-full gap-6 lg:grid-cols-[minmax(0,1.15fr)_420px]">
        <section class="hidden rounded-[2rem] border border-[#ddd2c3] dark:border-white/10 bg-white/70 dark:bg-white/5 p-10 shadow-[0_28px_80px_rgba(77,53,24,0.08)] backdrop-blur lg:block">
          <p class="text-sm font-semibold uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">
            {{ $t('forgotPassword.sectionTitle') }}
          </p>
          <h1 class="mt-5 text-5xl font-semibold leading-[1.02] tracking-[-0.04em] text-slate-950 dark:text-white">
            {{ $t('forgotPassword.heroTitle') }}
          </h1>
          <p class="mt-6 max-w-lg text-base leading-8 text-slate-600 dark:text-slate-400">
            {{ $t('forgotPassword.heroDesc') }}
          </p>
        </section>

        <Card class="border-[#ddd2c3] dark:border-white/10 bg-white dark:bg-[#262626] shadow-[0_25px_80px_rgba(77,53,24,0.08)]">
          <CardHeader class="space-y-3">
            <CardTitle class="text-3xl dark:text-white">{{ $t('forgotPassword.title') }}</CardTitle>
            <CardDescription>{{ $t('forgotPassword.desc') }}</CardDescription>
          </CardHeader>
          <CardContent class="space-y-5">
            <div class="space-y-2">
              <label class="text-sm font-medium text-slate-700 dark:text-slate-300">{{ $t('forgotPassword.email') }}</label>
              <Input
                v-model="email"
                type="email"
                autocomplete="email"
                placeholder="you@example.com"
              />
            </div>

            <p
              v-if="error"
              class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400"
            >
              {{ error }}
            </p>

            <div
              v-if="successMessage"
              class="space-y-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400"
            >
              <p>{{ successMessage }}</p>
              <p class="break-all">
                <span class="font-semibold">{{ $t('forgotPassword.resetToken') }}:</span> {{ resetToken }}
              </p>
              <p class="break-all">
                <span class="font-semibold">{{ $t('forgotPassword.resetPath') }}:</span> {{ resetUrl }}
              </p>
            </div>

            <div class="grid gap-3">
              <Button
                class="h-11 w-full bg-slate-900 text-white hover:bg-slate-800"
                :disabled="loading"
                @click="submit"
              >
                {{ loading ? $t('forgotPassword.generating') : $t('forgotPassword.generateBtn') }}
              </Button>

              <Button
                variant="outline"
                class="h-11 w-full"
                :disabled="!resetToken"
                @click="goToReset"
              >
                {{ $t('forgotPassword.continueBtn') }}
              </Button>
            </div>

            <p class="text-center text-sm text-slate-500 dark:text-slate-400">
              {{ $t('forgotPassword.remembered') }}
              <NuxtLink to="/auth/login" class="font-semibold text-slate-900 dark:text-white hover:underline">
                {{ $t('forgotPassword.backToLogin') }}
              </NuxtLink>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  </main>
</template>
