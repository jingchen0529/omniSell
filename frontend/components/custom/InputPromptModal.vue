<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

defineOptions({
  name: "InputPromptModal",
});

const props = defineProps<{
  open: boolean;
  title: string;
  value: string;
  error: string;
  pending: boolean;
  placeholder?: string;
  description?: string;
  helper?: string;
  confirmText?: string;
  cancelText?: string;
  inputType?: "text" | "url";
  selectOnOpen?: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm"): void;
  (e: "update:value", value: string): void;
}>();

const inputRef = ref<HTMLInputElement | null>(null);

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      return;
    }

    await nextTick();
    const input = inputRef.value;
    if (!input) {
      return;
    }

    input.focus();
    if (props.selectOnOpen ?? true) {
      input.select();
      return;
    }

    const cursor = input.value.length;
    input.setSelectionRange(cursor, cursor);
  },
);
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-[160] flex items-center justify-center bg-black/20 px-3"
    @click.self="emit('close')"
  >
    <div
      class="w-full max-w-[560px] rounded-[12px] border border-[#d9d9d9] bg-white px-6 py-3 shadow-[0_28px_80px_rgba(15,23,42,0.18)]"
    >
      <div class="flex items-center justify-between gap-4">
        <h3 class="text-[13px] font-bold text-[#1f1f1f]">{{ title }}</h3>
        <button
          class="flex items-center justify-center w-10 h-10 rounded-full text-[#8b8b8b] hover:bg-[#f3f4f6] hover:text-[#4b5563] transition-colors"
          type="button"
          @click="emit('close')"
        >
          <LucideIcon
            name="X"
            class="w-4 h-4"
            :stroke-width="2.2"
          />
        </button>
      </div>

      <p
        v-if="description"
        class="mt-2 text-[12px] leading-5 text-[#6b7280]"
      >
        {{ description }}
      </p>

      <div class="mt-4">
        <input
          ref="inputRef"
          :value="value"
          :type="inputType || 'text'"
          :placeholder="placeholder"
          class="w-full rounded-md border border-[#d1d5db] bg-white px-3 py-2 text-[14px] text-[#1f1f1f] outline-none transition-colors focus:border-[#2563eb] focus:ring-2 focus:ring-[#dbeafe]"
          @input="emit('update:value', ($event.target as HTMLInputElement).value)"
          @keydown.enter.prevent="emit('confirm')"
          @keydown.esc.prevent="emit('close')"
        />
        <p
          v-if="error"
          class="mt-3 text-[14px] font-medium text-[#dc2626]"
        >
          {{ error }}
        </p>
        <p
          v-else-if="helper"
          class="mt-3 text-[12px] leading-5 text-[#6b7280]"
        >
          {{ helper }}
        </p>
      </div>

      <div class="mt-4 flex items-center justify-end gap-3">
        <button
          class="min-w-[36px] rounded-[12px] border border-[#e5e7eb] bg-white px-4 py-2 text-[14px] font-semibold text-[#1f1f1f] hover:bg-[#f9fafb] transition-colors"
          type="button"
          @click="emit('close')"
        >
          {{ cancelText || "取消" }}
        </button>
        <button
          :disabled="pending"
          class="min-w-[36px] rounded-[12px] bg-[#2563eb] px-4 py-2 text-[14px] font-semibold text-white shadow-[0_14px_32px_rgba(37,99,235,0.28)] hover:bg-[#1d4ed8] disabled:cursor-not-allowed disabled:opacity-70 transition-colors"
          type="button"
          @click="emit('confirm')"
        >
          <span
            v-if="!pending"
            class="inline-flex items-center justify-center"
          >
            {{ confirmText || "确定" }}
          </span>
          <span
            v-else
            class="inline-flex items-center justify-center"
          >
            <LucideIcon
              name="Loader2"
              class="w-5 h-5 animate-spin"
            />
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
