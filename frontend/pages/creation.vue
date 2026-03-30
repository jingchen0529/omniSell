<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";

definePageMeta({
  layout: "console",
  middleware: "auth",
  ssr: false,
});

const { t } = useI18n();
const api = useOmniSellApi();
const router = useRouter();

// Reset project when entering specialized entry page to prevent header cache
onMounted(() => {
  const { selectedProject } = useChatStore();
  selectedProject.value = null;
});

useHead({
  title: "创作爆款",
});

const prefillText = `我希望创作的视频类型：[UGC种草/产品口播/产品演示/痛点-解决/前后对比/反应展示/故事讲述]
我的目标客群：[种族/地区/职业/生理特征等]
我的商品名称：
我的商品卖点：
我倾向的视频风格：`;

const inputText = ref(prefillText);
const sending = ref(false);
const errorMessage = ref("");
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const resizeTextarea = () => {
  const textarea = textareaRef.value;
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 260)}px`;
};

const canSend = computed(() => {
  if (sending.value) return false;
  return inputText.value.trim().length >= 2;
});

const handleSend = async () => {
  errorMessage.value = "";
  if (!canSend.value) return;

  sending.value = true;
  try {
    const project = await api<any>("/projects", {
      method: "POST",
      body: {
        source_url: "",
        title: `创作爆款 · 新脚本文案`,
        objective: inputText.value.trim(),
        workflow_type: "create",
      },
    });
    await router.push({ path: "/new-chat", query: { projectId: project.id } });
  } catch (error: any) {
    const detail = error?.data?.detail || error?.message || "发送失败";
    errorMessage.value = detail;
  } finally {
    sending.value = false;
  }
};
</script>

<template>
  <div
    class="flex-1 flex flex-col h-full relative bg-[#ffffff] dark:bg-[#121212]"
  >
    <!-- Empty space above -->
    <div class="flex-1"></div>

    <!-- Bottom Input Area -->
    <div
      class="absolute bottom-0 left-0 right-0 p-4 lg:px-[120px] bg-gradient-to-t from-white via-white dark:from-[#121212] dark:via-[#121212] to-transparent pointer-events-none pb-8"
    >
      <div class="max-w-[800px] mx-auto pointer-events-auto">
        <div
          v-if="errorMessage"
          class="mb-2 px-4 py-2 bg-red-50 text-red-600 rounded-xl text-sm border border-red-100 flex items-center gap-2 mx-auto w-fit shadow-sm"
        >
          <LucideIcon name="AlertCircle" class="w-4 h-4" />
          {{ errorMessage }}
        </div>

        <div
          class="relative rounded-3xl bg-white dark:bg-[#1f1f1f] border border-[#e5e5e5] dark:border-white/10 shadow-[0_4px_30px_rgba(0,0,0,0.06)] dark:shadow-[0_4px_30px_rgba(0,0,0,0.3)] transition-all overflow-visible focus-within:ring-2 focus-within:ring-blue-100 dark:focus-within:ring-blue-500/20 focus-within:border-blue-300 dark:focus-within:border-blue-500/50"
        >
          <textarea
            ref="textareaRef"
            v-model="inputText"
            rows="1"
            class="w-full bg-transparent resize-none outline-none px-5 py-3.5 text-[15px] text-[#1a1a1a] dark:text-white placeholder-[#999] max-h-[260px] custom-scrollbar leading-relaxed"
            placeholder="输入你想让 AI 帮忙的指令..."
            style="min-height: 52px"
            @input="resizeTextarea"
            @keydown.enter.meta.prevent="handleSend"
            @keydown.enter.ctrl.prevent="handleSend"
          />

          <!-- Tools Row -->
          <div
            class="flex items-center justify-between px-3 py-2 relative z-[100] border-t border-transparent"
          >
            <div class="flex items-center gap-1.5 relative flex-wrap">
              <!-- Mode Tag -->
              <div
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 text-[13px] font-medium border border-blue-100 dark:border-blue-500/20 shadow-sm cursor-default"
              >
                <LucideIcon name="Sparkles" class="w-4 h-4 ml-0.5" />
                <span>创作爆款</span>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <button
                @click="handleSend"
                :disabled="!canSend"
                :class="
                  canSend
                    ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-500 cursor-not-allowed'
                "
                class="w-[34px] h-[34px] rounded-full flex items-center justify-center transition-all duration-200"
              >
                <LucideIcon
                  v-if="!sending"
                  name="ArrowUp"
                  class="w-[18px] h-[18px]"
                  stroke-width="2.5"
                />
                <LucideIcon
                  v-else
                  name="Loader2"
                  class="w-[18px] h-[18px] animate-spin"
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(153, 153, 153, 0.3);
  border-radius: 20px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(153, 153, 153, 0.5);
}
</style>
