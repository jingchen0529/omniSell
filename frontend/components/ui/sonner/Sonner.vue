<script lang="ts" setup>
import { computed, watch } from "vue";
import {
  dismissToast,
  setToastDefaults,
  toastState,
  type ToastItem,
  type ToastVariant,
} from "./toast";

type ToasterPosition =
  | "top-left"
  | "top-center"
  | "top-right"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right";

type ToasterProps = {
  position?: ToasterPosition;
  duration?: number;
  richColors?: boolean;
  closeButton?: boolean;
};

const props = withDefaults(defineProps<ToasterProps>(), {
  position: "top-right",
  duration: 3000,
  richColors: false,
  closeButton: false,
});

watch(
  () => props.duration,
  (duration) => {
    setToastDefaults({ duration });
  },
  { immediate: true },
);

const positionClass = computed(() => {
  const positions: Record<ToasterPosition, string> = {
    "top-left": "left-0 top-0 items-start",
    "top-center": "left-1/2 top-0 -translate-x-1/2 items-center",
    "top-right": "right-0 top-0 items-end",
    "bottom-left": "bottom-0 left-0 items-start",
    "bottom-center": "bottom-0 left-1/2 -translate-x-1/2 items-center",
    "bottom-right": "bottom-0 right-0 items-end",
  };

  return positions[props.position];
});

const iconNameMap: Record<ToastVariant, string> = {
  info: "Info",
  success: "CheckCircle2",
  error: "CircleAlert",
};

const iconWrapClassMap: Record<ToastVariant, string> = {
  info: "bg-slate-900/8 text-slate-700 dark:bg-white/10 dark:text-slate-200",
  success:
    "bg-emerald-600/12 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  error: "bg-rose-600/12 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
};

const toastClassMap: Record<ToastVariant, { plain: string; rich: string }> = {
  info: {
    plain:
      "border-slate-200/90 bg-white/95 text-slate-900 dark:border-white/10 dark:bg-[#262626]/95 dark:text-slate-100",
    rich:
      "border-slate-300 bg-slate-900 text-white dark:border-white/10 dark:bg-white dark:text-slate-900",
  },
  success: {
    plain:
      "border-emerald-200 bg-emerald-50/95 text-emerald-900 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-100",
    rich:
      "border-emerald-600 bg-emerald-600 text-white dark:border-emerald-500 dark:bg-emerald-500 dark:text-white",
  },
  error: {
    plain:
      "border-rose-200 bg-rose-50/95 text-rose-900 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-100",
    rich:
      "border-rose-600 bg-rose-600 text-white dark:border-rose-500 dark:bg-rose-500 dark:text-white",
  },
};

const getIconName = (variant: ToastVariant) => iconNameMap[variant];

const getIconWrapClass = (variant: ToastVariant) => iconWrapClassMap[variant];

const getToastClass = (item: ToastItem) =>
  props.richColors
    ? toastClassMap[item.variant].rich
    : toastClassMap[item.variant].plain;
</script>

<template>
  <Teleport to="body">
    <div
      class="pointer-events-none fixed z-[260] flex w-full max-w-[420px] flex-col gap-3 p-4"
      :class="positionClass"
    >
      <TransitionGroup name="toast-list">
        <div
          v-for="item in toastState.items"
          :key="item.id"
          class="pointer-events-auto w-full overflow-hidden rounded-2xl border shadow-[0_20px_50px_rgba(15,23,42,0.18)] backdrop-blur"
          :class="getToastClass(item)"
        >
          <div class="flex items-start gap-3 px-4 py-3.5">
            <div
              class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
              :class="getIconWrapClass(item.variant)"
            >
              <LucideIcon :name="getIconName(item.variant)" class="h-4 w-4" />
            </div>

            <div class="min-w-0 flex-1">
              <div class="text-sm font-semibold leading-5">
                {{ item.title }}
              </div>
              <div
                v-if="item.description"
                class="mt-1 text-xs leading-5 opacity-80"
              >
                {{ item.description }}
              </div>
            </div>

            <button
              v-if="closeButton"
              type="button"
              class="rounded-full p-1 text-current/70 transition hover:bg-black/6 hover:text-current dark:hover:bg-white/8"
              @click="dismissToast(item.id)"
            >
              <LucideIcon name="X" class="h-4 w-4" />
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-list-enter-active,
.toast-list-leave-active {
  transition: all 0.22s ease;
}

.toast-list-enter-from,
.toast-list-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.98);
}

.toast-list-move {
  transition: transform 0.22s ease;
}
</style>
