<script setup lang="ts">
import { ref, computed } from "vue";

const props = defineProps<{
  tasks: any[];
  summary: string;
  isFailed: boolean;
  failedReason?: string;
}>();

const expanded = ref(true);

const getTaskStatusLabel = (status: string) => {
  if (status === "completed") return "已完成";
  if (status === "in_progress") return "进行中";
  if (status === "failed") return "失败";
  return "待执行";
};
const getTaskStatusTextClass = (status: string) => {
  if (status === "completed") return "text-[#10b981]";
  if (status === "in_progress") return "text-blue-500";
  if (status === "failed") return "text-rose-500";
  return "text-slate-400";
};
const getTaskMarkerClass = (status: string) => {
  if (status === "completed") return "text-[#10b981]";
  if (status === "in_progress") return "text-blue-500";
  if (status === "failed") return "text-rose-500";
  return "text-[#d1d5db]";
};
const getTaskIconName = (status: string) => {
  if (status === "completed") return "CircleCheck";
  if (status === "in_progress") return "LoaderCircle";
  if (status === "failed") return "AlertCircle";
  return "Circle";
};
const getTaskIconClass = (status: string) =>
  status === "in_progress" ? "animate-spin" : "";
  
const failedTask = computed(() => props.tasks.find(t => t.status === "failed"));
</script>

<template>
  <div v-if="tasks.length > 0" class="mb-6">
    <button
      class="flex items-center gap-1.5 text-left text-[14.5px] font-medium text-[#1a1a1a] dark:text-gray-200"
      @click="expanded = !expanded"
    >
      <LucideIcon
        :name="isFailed ? 'AlertCircle' : 'ListTodo'"
        class="h-[15px] w-[15px]"
        :class="isFailed ? 'text-rose-500' : 'text-blue-500'"
        :stroke-width="2"
      />
      <span>{{ summary }}</span>
      <LucideIcon
        :name="expanded ? 'ChevronUp' : 'ChevronDown'"
        class="h-4 w-4 shrink-0 text-[#999]"
        :stroke-width="2"
      />
    </button>

    <div v-if="expanded" class="relative mt-4 pl-[3px]">
      <div
        v-for="(task, index) in tasks"
        :key="task.id"
        class="relative pb-4 last:pb-0 flex items-start gap-2.5"
      >
        <div
          v-if="index !== tasks.length - 1"
          class="absolute left-[8px] top-6 bottom-[-5px] w-[2px] bg-[#f0f0f0] dark:bg-white/10"
        ></div>

        <div
          class="relative z-10 flex h-[18px] w-[18px] mt-[1px] items-center justify-center bg-transparent"
          :class="getTaskMarkerClass(task.status)"
        >
          <LucideIcon
            :name="getTaskIconName(task.status)"
            class="h-[17px] w-[17px]"
            :class="getTaskIconClass(task.status)"
            :stroke-width="1.8"
          />
        </div>

        <div class="min-w-0 flex-1 flex flex-col pt-[0.5px]">
          <div
            class="flex items-center justify-between gap-2 max-w-[400px]"
          >
            <div
              class="text-[14.5px] font-medium text-[#1a1a1a] dark:text-white truncate"
            >
              {{ task.title }}
            </div>
            <div
              class="text-[13px] font-medium shrink-0"
              :class="getTaskStatusTextClass(task.status)"
            >
              {{ getTaskStatusLabel(task.status) }}
            </div>
          </div>
          <div
            class="mt-0.5 text-[13.5px] text-[#6b7280] dark:text-[#9ca3af] flex items-center gap-1"
          >
            {{ task.detail }}
          </div>
          <div
            v-if="task.error_detail"
            class="mt-1 text-[13px] text-rose-600 dark:text-rose-400"
          >
            {{ task.error_detail }}
          </div>
        </div>
      </div>
    </div>
    <div
      v-if="isFailed && (failedTask || failedReason)"
      class="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200"
    >
      {{ failedTask?.error_detail || failedReason }}
    </div>
  </div>
</template>
