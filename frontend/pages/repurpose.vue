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
  title: "复刻爆款",
});

const prefillText = "复刻这个视频的画面细节，包括画面构图、色彩、光影等：";
const inputText = ref(prefillText);
const sending = ref(false);
const errorMessage = ref("");
const selectedFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const videoFileExtensions = [".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg"];
const sourceVideoAccept = "video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v,.mpeg,.mpg";

const hasFileExtension = (filename: string, extensions: string[]) => {
  const lowerName = filename.toLowerCase();
  return extensions.some((ext) => lowerName.endsWith(ext));
};

const isVideoFile = (file: { name: string; type?: string | null }) =>
  (file.type || "").startsWith("video/") || hasFileExtension(file.name, videoFileExtensions);

const handleUploadClick = () => {
  fileInputRef.value?.click();
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  target.value = "";
  errorMessage.value = "";
  if (!file) return;

  if (!isVideoFile(file)) {
    errorMessage.value = "当前只支持上传视频文件。";
    return;
  }
  selectedFile.value = file;
};

const clearSelectedSource = () => {
  if (selectedFile.value) {
    selectedFile.value = null;
    if (fileInputRef.value) fileInputRef.value.value = "";
  }
};

const resizeTextarea = () => {
  const textarea = textareaRef.value;
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
};

const canSend = computed(() => {
  return !sending.value && selectedFile.value !== null && inputText.value.trim().length >= 2;
});

const handleSend = async () => {
  errorMessage.value = "";
  if (!canSend.value) return;

  sending.value = true;
  try {
    let project: any;
    const formData = new FormData();
    if (selectedFile.value) {
        formData.append("file", selectedFile.value);
        formData.append("title", `复刻爆款 · ${selectedFile.value.name}`);
        formData.append("objective", inputText.value.trim());
        formData.append("workflow_type", "remake");
        project = await api("/projects/upload", { method: "POST", body: formData });
    } else {
        throw new Error("请先上传对标视频。");
    }
    
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
  <div class="flex-1 flex flex-col h-full relative bg-[#ffffff] dark:bg-[#121212]">
    <div class="flex-1"></div>

    <!-- Bottom Input Area -->
    <div class="absolute bottom-0 left-0 right-0 p-4 lg:px-[120px] bg-gradient-to-t from-white via-white dark:from-[#121212] dark:via-[#121212] to-transparent pointer-events-none pb-8">
      <div class="max-w-[800px] mx-auto pointer-events-auto">
        <div v-if="errorMessage" class="mb-2 px-4 py-2 bg-red-50 text-red-600 rounded-xl text-sm border border-red-100 flex items-center gap-2 mx-auto w-fit shadow-sm">
          <LucideIcon name="AlertCircle" class="w-4 h-4" />
          {{ errorMessage }}
        </div>

        <div class="relative rounded-3xl bg-white dark:bg-[#1f1f1f] border border-[#e5e5e5] dark:border-white/10 shadow-[0_4px_30px_rgba(0,0,0,0.06)] dark:shadow-[0_4px_30px_rgba(0,0,0,0.3)] transition-all overflow-visible focus-within:ring-2 focus-within:ring-blue-100 dark:focus-within:ring-blue-500/20 focus-within:border-blue-300 dark:focus-within:border-blue-500/50">
          
          <div v-if="selectedFile" class="px-4 pt-4 pb-1 flex flex-wrap gap-2">
            <div class="inline-flex items-center gap-2.5 rounded-2xl border border-[#ececec] bg-white px-3 py-2 shadow-[0_4px_12px_rgba(15,23,42,0.05)] max-w-[320px]">
              <div class="flex items-center justify-center w-9 h-9 rounded-full bg-[#efefef] text-[#3f3f46] shrink-0">
                <LucideIcon name="Video" class="w-4 h-4" :stroke-width="1.8" />
              </div>
              <div class="flex-1 min-w-0 overflow-hidden">
                <div class="text-[15px] font-semibold text-[#1a1a1a] leading-tight">{{ selectedFile.name }}</div>
                <div class="text-[13px] text-[#9ca3af] truncate leading-tight mt-0.5">本地视频</div>
              </div>
              <button @click.stop.prevent="clearSelectedSource()" class="flex items-center justify-center w-8 h-8 rounded-full text-[#9ca3af] hover:bg-[#f3f4f6] hover:text-[#6b7280] transition-colors shrink-0 z-10 relative">
                <LucideIcon name="X" class="w-5 h-5" :stroke-width="2" />
              </button>
            </div>
          </div>

          <textarea
            ref="textareaRef"
            v-model="inputText"
            rows="1"
            class="w-full bg-transparent resize-none outline-none px-5 py-3.5 text-[15px] text-[#1a1a1a] dark:text-white placeholder-[#999] max-h-[160px] custom-scrollbar leading-relaxed"
            placeholder="输入你想让 AI 帮忙的指令..."
            style="min-height: 52px"
            @input="resizeTextarea"
            @keydown.enter.meta.prevent="handleSend"
            @keydown.enter.ctrl.prevent="handleSend"
          />

          <!-- Tools Row -->
          <div class="flex items-center justify-between px-3 py-2 relative z-[100] border-t border-transparent">
            <div class="flex items-center gap-1.5 relative flex-wrap">
              <!-- Mode Tag -->
              <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 text-[13px] font-medium border border-blue-100 dark:border-blue-500/20 shadow-sm cursor-default">
                <LucideIcon name="Video" class="w-4 h-4 ml-0.5" />
                <span>复刻爆款</span>
              </div>

              <div class="w-[1px] h-4 bg-slate-200 dark:bg-white/10 mx-2"></div>

              <!-- Attach Buttons -->
              <button @click="handleUploadClick" :disabled="selectedFile !== null" class="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 rounded-full transition-colors text-[13px] disabled:opacity-50 disabled:cursor-not-allowed">
                <LucideIcon name="Paperclip" class="w-[18px] h-[18px]" stroke-width="1.8" />
                <span>上传视频</span>
              </button>
            </div>

            <!-- Send button -->
            <div class="flex items-center gap-2">
              <button
                @click="handleSend"
                :disabled="!canSend"
                :class="canSend ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm' : 'bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-500 cursor-not-allowed'"
                class="w-[34px] h-[34px] rounded-full flex items-center justify-center transition-all duration-200"
              >
                <LucideIcon v-if="!sending" name="ArrowUp" class="w-[18px] h-[18px]" stroke-width="2.5" />
                <LucideIcon v-else name="Loader2" class="w-[18px] h-[18px] animate-spin" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <input ref="fileInputRef" type="file" class="hidden" accept="video/*" @change="handleFileChange" />
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
