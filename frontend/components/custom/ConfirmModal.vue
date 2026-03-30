<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-[160] flex items-center flex-col justify-center bg-black/20 px-3"
    @click.self="onCancel"
  >
    <div
      class="w-full max-w-[400px] rounded-[16px] border border-[#d9d9d9] dark:border-white/10 bg-white dark:bg-[#1f1f1f] px-6 py-5 shadow-[0_28px_80px_rgba(0,0,0,0.18)]"
    >
      <div class="flex items-center justify-between gap-4 mb-2">
        <h3 class="text-[15px] font-bold text-[#1f1f1f] dark:text-white">{{ title }}</h3>
        <button
          class="flex items-center justify-center w-8 h-8 rounded-full text-[#8b8b8b] hover:bg-[#f3f4f6] dark:hover:bg-white/10 transition-colors"
          @click="onCancel"
        >
          <LucideIcon name="X" class="w-4 h-4" :stroke-width="2.2" />
        </button>
      </div>

      <p class="text-[13px] text-[#6b7280] dark:text-[#9ca3af] mb-6 whitespace-pre-line">
        {{ message }}
      </p>

      <div class="flex items-center justify-end gap-3 font-medium">
        <button
          class="min-w-[72px] rounded-xl border border-[#e5e7eb] dark:border-white/10 bg-white dark:bg-[#262626] px-4 py-2 text-[13px] text-[#1f1f1f] dark:text-white hover:bg-[#f9fafb] dark:hover:bg-white/5 transition-colors"
          @click="onCancel"
          :disabled="loading"
        >
          {{ cancelText }}
        </button>
        <button
          class="min-w-[72px] rounded-xl bg-red-600 px-4 py-2 text-[13px] text-white hover:bg-red-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1.5"
          @click="onConfirm"
          :disabled="loading"
        >
          <LucideIcon
            v-if="loading"
            name="Loader2"
            class="w-4 h-4 animate-spin"
          />
          {{ confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import LucideIcon from "~/components/custom/LucideIcon.vue";

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  cancelText: {
    type: String,
    default: "取消",
  },
  confirmText: {
    type: String,
    default: "确认",
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue", "confirm", "cancel"]);

const onCancel = () => {
  if (props.loading) return;
  emit("update:modelValue", false);
  emit("cancel");
};

const onConfirm = () => {
  if (props.loading) return;
  emit("confirm");
};
</script>
