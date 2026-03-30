<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import PeekCharacters from "@/components/custom/PeekCharacters.vue";

const { t } = useI18n();

definePageMeta({
  middleware: "guest",
});

const auth = useAuth();
const router = useRouter();

const form = reactive({
  displayName: "",
  email: "",
  password: "",
  confirmPassword: "",
});

const loading = ref(false);
const showPassword = ref(false);
const showConfirmPassword = ref(false);
const isTyping = ref(false);
const passwordFocused = ref(false);
const error = ref("");
const successMessage = ref("");

const passwordLength = computed(() =>
  Math.max(form.password.length, form.confirmPassword.length),
);
const isPasswordGuardMode = computed(() => passwordFocused.value);

const handleSubmit = async () => {
  error.value = "";
  successMessage.value = "";

  if (form.displayName.trim().length < 2) {
    error.value = t('register.errorNameShort');
    return;
  }

  if (!form.email.trim()) {
    error.value = t('register.errorEmailRequired');
    return;
  }

  if (form.password.trim().length < 8) {
    error.value = t('register.errorPasswordShort');
    return;
  }

  if (form.password !== form.confirmPassword) {
    error.value = t('register.errorPasswordMismatch');
    return;
  }

  loading.value = true;

  try {
    const user = await auth.register({
      display_name: form.displayName.trim(),
      email: form.email.trim(),
      password: form.password,
    });
    successMessage.value = t('register.registerSuccess', { name: user.display_name });
    await router.push("/");
  } catch (submitError: unknown) {
    if (submitError && typeof submitError === "object") {
      const detail = (submitError as { data?: { detail?: string } }).data?.detail;
      if (detail) {
        error.value = detail;
      } else {
        const message = (submitError as { message?: string }).message;
        error.value = message || t('register.registerFailed');
      }
    } else {
      error.value = t('register.registerFailed');
    }
  } finally {
    loading.value = false;
  }
};

useHead({
  title: computed(() => t('register.pageTitle')),
});
</script>

<template>
  <main class="login-page">
    <div class="login-container">
      <section class="left-panel">
        <div class="left-top">
          <div class="brand-mark">
            <div class="brand-mark-inner">
              <img
                src="~/assets/image/icon.webp"
                alt="Brand Logo"
                class="brand-icon"
              />
            </div>
          </div>
          <span class="brand-name">OmniSell Video Lab</span>
        </div>

        <div class="characters-area">
          <div class="characters-stage">
            <PeekCharacters
              :is-typing="isTyping"
              :show-password="showPassword || showConfirmPassword"
              :password-length="passwordLength"
              :is-password-guard-mode="isPasswordGuardMode"
            />
          </div>
        </div>

        <div class="left-footer">
          <a href="#" class="footer-link">Privacy Policy</a>
          <a href="#" class="footer-link">Terms of Service</a>
        </div>

        <button type="button" class="check-fab" aria-label="Complete">
          <LucideIcon name="Check" class="check-icon" aria-hidden="true" :stroke-width="2" />
        </button>

        <div class="decor-blur decor-blur-one" />
        <div class="decor-blur decor-blur-two" />
      </section>

      <section class="right-panel">
        <div class="form-wrapper">
          <div class="mobile-logo">
            <div class="mobile-logo-icon">
              <img
                src="~/assets/image/icon.webp"
                alt="Mobile Logo"
                class="mobile-logo-svg"
              />
            </div>
            <span>OmniSell Video Lab</span>
          </div>

          <div class="form-header">
            <h1 class="form-title">{{ $t('register.title') }}</h1>
            <p class="form-subtitle">{{ $t('register.subtitle') }}</p>
          </div>

          <form class="form" @submit.prevent="handleSubmit">
            <div class="field-label">{{ $t('register.displayName') }}</div>
            <div class="input-wrap">
              <input
                v-model="form.displayName"
                type="text"
                autocomplete="name"
                :placeholder="$t('register.displayNamePlaceholder')"
                class="text-input"
                @focus="isTyping = true"
                @blur="isTyping = false"
              />
            </div>

            <div class="field-label">{{ $t('register.email') }}</div>
            <div class="input-wrap">
              <input
                v-model="form.email"
                type="email"
                autocomplete="email"
                placeholder="you@example.com"
                class="text-input"
                @focus="isTyping = true"
                @blur="isTyping = false"
              />
            </div>

            <div class="field-label">{{ $t('register.password') }}</div>
            <div class="input-wrap">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                :placeholder="$t('register.passwordPlaceholder')"
                class="text-input"
                @focus="passwordFocused = true"
                @blur="passwordFocused = false"
              />
              <button
                type="button"
                class="eye-toggle"
                @click="showPassword = !showPassword"
              >
                <LucideIcon
                  v-if="showPassword"
                  name="EyeOff"
                  class="eye-icon"
                  aria-hidden="true"
                  :stroke-width="2"
                />
                <LucideIcon
                  v-else
                  name="Eye"
                  class="eye-icon"
                  aria-hidden="true"
                  :stroke-width="2"
                />
              </button>
            </div>

            <div class="field-label">{{ $t('register.confirmPassword') }}</div>
            <div class="input-wrap">
              <input
                v-model="form.confirmPassword"
                :type="showConfirmPassword ? 'text' : 'password'"
                autocomplete="new-password"
                :placeholder="$t('register.confirmPasswordPlaceholder')"
                class="text-input"
                @focus="passwordFocused = true"
                @blur="passwordFocused = false"
              />
              <button
                type="button"
                class="eye-toggle"
                @click="showConfirmPassword = !showConfirmPassword"
              >
                <LucideIcon
                  v-if="showConfirmPassword"
                  name="EyeOff"
                  class="eye-icon"
                  aria-hidden="true"
                  :stroke-width="2"
                />
                <LucideIcon
                  v-else
                  name="Eye"
                  class="eye-icon"
                  aria-hidden="true"
                  :stroke-width="2"
                />
              </button>
            </div>

            <p v-if="error" class="feedback error-box">{{ error }}</p>
            <p v-if="successMessage" class="feedback success-box">
              {{ successMessage }}
            </p>

            <button type="submit" class="submit-btn" :disabled="loading">
              {{ loading ? $t('register.creating') : $t('register.createBtn') }}
            </button>

            <p class="signup-hint">
              {{ $t('register.hasAccount') }}
              <NuxtLink to="/auth/login" class="signup-link">{{ $t('register.loginLink') }}</NuxtLink>
            </p>
          </form>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  background: #ffffff;
}

.login-container {
  width: 100%;
  max-width: none;
  min-height: 100vh;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: 50% 50%;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.left-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  padding: 48px 48px 32px;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.18), transparent 34%),
    linear-gradient(180deg, #959dac 0%, #6f7889 100%);

  @media (max-width: 1024px) {
    display: none;
  }

  .left-top {
    position: relative;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 12px;
    color: #fff;

    .brand-mark {
      display: flex;
      height: 32px;
      width: 32px;
      align-items: center;
      justify-content: center;
      border-radius: 10px;
      backdrop-filter: blur(8px);

      &-inner {
        display: flex;
        height: 32px;
        width: 32px;
        align-items: center;
        justify-content: center;
        border-radius: 999px;

        .brand-icon {
          width: 32px;
          height: 32px;
          fill: white;
        }
      }
    }

    .brand-name {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
    }
  }

  .characters-area {
    position: relative;
    z-index: 20;
    display: flex;
    flex: 1;
    align-items: flex-end;
    justify-content: flex-start;
    min-height: 500px;
    padding-bottom: 0;
    overflow: visible;

    .characters-stage {
      display: flex;
      align-items: flex-end;
      justify-content: flex-start;
      width: 100%;
      height: 100%;

      :deep(.characters-root) {
        transform: scale(1);
        transform-origin: left bottom;
      }
    }
  }

  .left-footer {
    position: relative;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 32px;
    color: rgba(71, 80, 98, 0.6);
    font-size: 14px;

    .footer-link {
      color: inherit;
      text-decoration: none;
      transition: color 0.2s ease;

      &:hover {
        color: white;
      }
    }
  }

  .check-fab {
    position: absolute;
    right: 48px;
    bottom: 32px;
    z-index: 30;
    display: flex;
    height: 48px;
    width: 48px;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: 999px;
    background: #22c55e;
    box-shadow: 0 8px 16px rgba(34, 197, 94, 0.2);
    cursor: pointer;

    .check-icon {
      width: 24px;
      height: 24px;
      color: white;
    }
  }

  .decor-blur {
    position: absolute;
    border-radius: 999px;
    filter: blur(90px);
    pointer-events: none;

    &-one {
      top: 18%;
      right: 8%;
      width: 360px;
      height: 360px;
      background: rgba(255, 255, 255, 0.12);
    }

    &-two {
      left: 10%;
      bottom: 24%;
      width: 460px;
      height: 460px;
      background: rgba(119, 128, 145, 0.26);
    }
  }
}

.right-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 48px;
  background: #ffffff;

  @media (max-width: 1024px) {
    padding: 32px 24px;
  }

  .form-wrapper {
    width: 100%;
    max-width: 420px;

    @media (max-width: 1024px) {
      max-width: 400px;
      padding: 0;
    }
  }

  .mobile-logo {
    display: none;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 24px;
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;

    @media (max-width: 1024px) {
      display: flex;
    }

    &-icon {
      display: flex;
      width: 32px;
      height: 32px;
      align-items: center;
      justify-content: center;
      border-radius: 12px;

      .mobile-logo-svg {
        width: 32px;
        height: 32px;
        fill: white;
      }
    }
  }

  .form-header {
    text-align: center;

    .form-title {
      margin: 0;
      color: #030712;
      font-size: 32px;
      font-weight: 700;
      line-height: 1.2;
      letter-spacing: -0.02em;

      @media (max-width: 1024px) {
        font-size: 28px;
      }
    }

    .form-subtitle {
      margin: 8px 0 0;
      color: #70819f;
      font-size: 16px;
      line-height: 1.45;

      @media (max-width: 1024px) {
        font-size: 15px;
      }
    }
  }

  .form {
    margin-top: 40px;

    .field-label {
      margin-bottom: 8px;
      color: #111827;
      font-size: 14px;
      font-weight: 600;
    }

    .input-wrap {
      display: flex;
      align-items: center;
      gap: 12px;
      height: 48px;
      margin-bottom: 24px;
      padding: 0 16px;
      border-radius: 999px;
      border: 1px solid #e3e8f2;
      background: #ffffff;
      transition:
        border-color 0.2s ease,
        box-shadow 0.2s ease,
        background 0.2s ease;

      &:focus-within {
        border-color: #cdd8ee;
        background: white;
        box-shadow: 0 6px 16px rgba(34, 48, 73, 0.06);
      }

      .text-input {
        width: 100%;
        border: 0;
        background: transparent;
        color: #0f172a;
        font-size: 14px;
        outline: none;

        &::placeholder {
          color: #9ca3af;
        }
      }

      .eye-toggle {
        border: 0;
        background: transparent;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #9ca3af;
        cursor: pointer;
        padding: 0;

        .eye-icon {
          width: 20px;
          height: 20px;
          fill: currentColor;
        }
      }
    }

    .feedback {
      margin: 0 0 16px;
      padding: 12px 14px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.6;

      &.error-box {
        color: #b91c1c;
        background: #fff1f2;
        border: 1px solid #fecdd3;
      }

      &.success-box {
        color: #047857;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
      }
    }

    .submit-btn {
      width: 100%;
      height: 48px;
      border-radius: 999px;
      border: 1px solid #e3e8f2;
      font-size: 16px;
      font-weight: 600;
      transition: all 0.2s ease;
      background: #ffffff;
      color: #111827;
      cursor: pointer;

      &:hover:not(:disabled) {
        background: #f9fafb;
      }

      &:disabled {
        opacity: 0.7;
        cursor: not-allowed;
      }
    }

    .signup-hint {
      margin: 32px 0 0;
      text-align: center;
      color: #6b7280;
      font-size: 14px;

      .signup-link {
        color: #111827;
        font-weight: 600;
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }
    }
  }
}
</style>
