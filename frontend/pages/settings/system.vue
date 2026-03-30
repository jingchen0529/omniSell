<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { toast } from '~/components/ui/sonner';

definePageMeta({
  layout: "console",
  middleware: "auth",
});

const api = useOmniSellApi();

useHead({
  title: '系统设置',
});

// AI Settings
const aiConfig = ref({
  ai_provider: 'openai',
  ai_api_key: '',
  ai_api_base: '',
  ai_chat_model: '',
  ai_api_key_configured: false,
  ai_api_key_source: '',
  ai_config_source: '',
});

// Video Settings
const videoConfig = ref({
  video_provider: 'qwen',
  video_api_key: '',
  video_api_base: '',
  video_model: '',
  video_image_to_video_model: '',
  video_text_to_video_model: '',
  video_api_key_configured: false,
  video_api_key_source: '',
});

// Proxy Settings
const proxyConfig = ref({
  proxy_ip: '',
  proxy_port: null as number | null,
});

const loading = ref(true);
const savingAi = ref(false);
const savingVideo = ref(false);
const savingProxy = ref(false);
const showAiApiKey = ref(false);
const showVideoApiKey = ref(false);

type FeedbackType = 'success' | 'error';

type FeedbackState = {
  type: FeedbackType;
  message: string;
};

const pageFeedback = ref<FeedbackState | null>(null);
const aiFeedback = ref<FeedbackState | null>(null);
const videoFeedback = ref<FeedbackState | null>(null);
const proxyFeedback = ref<FeedbackState | null>(null);

const aiProviders = [
  { value: 'openai', label: 'OpenAI 官方 / 兼容接口' },
  { value: 'doubao', label: '豆包 / 火山方舟' },
  { value: 'qwen', label: '通义千问 / DashScope' },
  { value: 'grok', label: 'Grok / xAI 接口' },
  { value: 'custom', label: '自定义 OpenAI 兼容服务' },
];

const videoProviders = [
  { value: 'openai', label: 'OpenAI 兼容视频接口（/v1/videos）' },
  { value: 'doubao', label: '豆包视频 / 火山方舟' },
  { value: 'qwen', label: '通义万相 / DashScope' },
  { value: 'kling', label: '可灵视频 / Kling' },
  { value: 'veo', label: 'Google Veo 视频' },
  { value: 'custom', label: '自定义 OpenAI 兼容视频服务' },
];

const videoProviderDefaults = {
  openai: {
    video_api_base: '',
    video_model: '',
    video_image_to_video_model: '',
    video_text_to_video_model: '',
  },
  doubao: {
    video_api_base: 'https://ark.cn-beijing.volces.com/api/v3',
    video_model: 'doubao-seedance-1-5-pro-251215',
    video_image_to_video_model: 'doubao-seedance-1-5-pro-251215',
    video_text_to_video_model: 'doubao-seedance-1-5-pro-251215',
  },
  qwen: {
    video_api_base: 'https://dashscope.aliyuncs.com/api/v1',
    video_model: 'wan2.6-i2v',
    video_image_to_video_model: 'wan2.6-i2v',
    video_text_to_video_model: 'wan2.6-t2v',
  },
  kling: {
    video_api_base: '',
    video_model: '',
    video_image_to_video_model: '',
    video_text_to_video_model: '',
  },
  veo: {
    video_api_base: '',
    video_model: '',
    video_image_to_video_model: '',
    video_text_to_video_model: '',
  },
  custom: {
    video_api_base: '',
    video_model: '',
    video_image_to_video_model: '',
    video_text_to_video_model: '',
  },
} as const;

type VideoProvider = keyof typeof videoProviderDefaults;

type VideoDefaultField = keyof (typeof videoProviderDefaults)[VideoProvider];

const getVideoProviderDefaults = (provider: string) =>
  videoProviderDefaults[(provider in videoProviderDefaults
    ? provider
    : 'qwen') as VideoProvider];

const normalizeVideoFieldValue = (value: string | null | undefined) =>
  (value || '').trim();

const applyVideoProviderDefaults = (
  provider: string,
  previousProvider?: string,
) => {
  const nextDefaults = getVideoProviderDefaults(provider);
  const previousDefaults = previousProvider
    ? getVideoProviderDefaults(previousProvider)
    : null;

  const syncField = (field: VideoDefaultField) => {
    const currentValue = normalizeVideoFieldValue(videoConfig.value[field]);
    const previousValue = previousDefaults
      ? normalizeVideoFieldValue(previousDefaults[field])
      : '';
    const nextValue = normalizeVideoFieldValue(nextDefaults[field]);

    if (!currentValue || currentValue === previousValue) {
      videoConfig.value[field] = nextValue;
    }
  };

  syncField('video_api_base');
  syncField('video_model');
  syncField('video_image_to_video_model');
  syncField('video_text_to_video_model');
};

const isOpenAIVideoProvider = computed(
  () => ['openai', 'custom'].includes(videoConfig.value.video_provider),
);

const isDashScopeVideoProvider = computed(
  () => videoConfig.value.video_provider === 'qwen',
);

const videoApiBasePlaceholder = computed(() =>
  isOpenAIVideoProvider.value
    ? '例如：https://your-provider.com/v1 或 https://your-provider.com/v1/videos'
    : isDashScopeVideoProvider.value
      ? '例如：https://dashscope.aliyuncs.com/api/v1 或完整的 /video-synthesis 地址'
      : '例如：https://ark.cn-beijing.volces.com/api/v3',
);

const videoModelPlaceholder = computed(() =>
  isOpenAIVideoProvider.value
    ? '例如：sora、wan2.2-i2v-plus、kling-v1'
    : isDashScopeVideoProvider.value
      ? '例如：wan2.6-i2v'
      : '例如：doubao-seedance-1-5-pro',
);

const videoProviderDescription = computed(() => {
  if (isOpenAIVideoProvider.value) {
    return '当前模式用于兼容第三方 OpenAI 风格的视频接口。你可以填写到 /v1，也可以直接填写完整的 /v1/videos，系统会自动规范化并请求 /videos。';
  }
  if (isDashScopeVideoProvider.value) {
    return 'DashScope 模式会请求 /api/v1/services/aigc/video-generation/video-synthesis，并轮询 /api/v1/tasks/{task_id}。你可以填写根域名、/api/v1，或完整 video-synthesis 地址，系统会自动兼容。';
  }
  return '豆包模式使用火山方舟的视频生成接口。若填写了完整任务地址，系统会自动裁剪成基础 API 地址。';
});

watch(
  () => videoConfig.value.video_provider,
  (provider, previousProvider) => {
    if (loading.value || provider === previousProvider) {
      return;
    }
    applyVideoProviderDefaults(provider, previousProvider);
  },
);

const getFeedbackClass = (type: FeedbackType) =>
  type === 'success'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300'
    : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300';

const getFeedbackIcon = (type: FeedbackType) =>
  type === 'success' ? 'CheckCircle2' : 'CircleAlert';

const getDetailMessage = (detail: unknown): string | null => {
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const message = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }

        if (
          item &&
          typeof item === 'object' &&
          'msg' in item &&
          typeof item.msg === 'string'
        ) {
          return item.msg;
        }

        return '';
      })
      .filter(Boolean)
      .join('；');

    return message || null;
  }

  return null;
};

const resolveErrorMessage = (error: unknown, fallback: string) => {
  const directDetail = getDetailMessage(
    (error as { data?: { detail?: unknown } })?.data?.detail,
  );
  if (directDetail) {
    return directDetail;
  }

  const responseDetail = getDetailMessage(
    (error as { response?: { _data?: { detail?: unknown } } })?.response?._data
      ?.detail,
  );
  if (responseDetail) {
    return responseDetail;
  }

  const message =
    (error as { message?: string })?.message?.trim() || '';

  return message || fallback;
};

const fetchSettings = async () => {
  loading.value = true;
  pageFeedback.value = null;
  try {
    const [ai, video, proxy] = await Promise.all([
      api('/system-settings/ai'),
      api('/system-settings/video'),
      api('/system-settings/proxy'),
    ]);
    
    aiConfig.value = {
      ...ai,
      ai_api_key: ai.ai_api_key || '',
    };
    
    videoConfig.value = {
      ...video,
      video_api_key: video.video_api_key || '',
    };
    
    proxyConfig.value = {
      proxy_ip: proxy.proxy_ip || '',
      proxy_port: proxy.proxy_port,
    };
  } catch (error) {
    console.error('Failed to fetch settings:', error);
    const message = resolveErrorMessage(
      error,
      '获取系统配置失败，请刷新页面后重试',
    );
    pageFeedback.value = {
      type: 'error',
      message,
    };
    toast.error(message);
  } finally {
    loading.value = false;
  }
};

const saveAiSettings = async () => {
  savingAi.value = true;
  aiFeedback.value = null;
  try {
    const res = await api('/system-settings/ai', {
      method: 'PUT',
      body: {
        ai_provider: aiConfig.value.ai_provider,
        ai_api_key: aiConfig.value.ai_api_key || null,
        ai_api_base: aiConfig.value.ai_api_base || null,
        ai_chat_model: aiConfig.value.ai_chat_model || null,
      },
    });
    aiConfig.value = {
      ...res,
      ai_api_key: res.ai_api_key || '',
    };
    const message = 'AI 配置已保存';
    aiFeedback.value = {
      type: 'success',
      message,
    };
    toast.success(message);
  } catch (error) {
    const message = resolveErrorMessage(
      error,
      'AI 配置保存失败，请检查网络或配置项',
    );
    aiFeedback.value = {
      type: 'error',
      message,
    };
    toast.error(message);
  } finally {
    savingAi.value = false;
  }
};

const saveVideoSettings = async () => {
  savingVideo.value = true;
  videoFeedback.value = null;
  try {
    const res = await api('/system-settings/video', {
      method: 'PUT',
      body: {
        video_provider: videoConfig.value.video_provider,
        video_api_key: videoConfig.value.video_api_key || null,
        video_api_base: videoConfig.value.video_api_base || null,
        video_model: videoConfig.value.video_model || null,
        video_image_to_video_model: videoConfig.value.video_image_to_video_model || null,
        video_text_to_video_model: videoConfig.value.video_text_to_video_model || null,
      },
    });
    videoConfig.value = {
      ...res,
      video_api_key: res.video_api_key || '',
    };
    const message = '视频配置已保存';
    videoFeedback.value = {
      type: 'success',
      message,
    };
    toast.success(message);
  } catch (error) {
    const message = resolveErrorMessage(
      error,
      '视频配置保存失败，请检查网络或配置项',
    );
    videoFeedback.value = {
      type: 'error',
      message,
    };
    toast.error(message);
  } finally {
    savingVideo.value = false;
  }
};

const saveProxySettings = async () => {
  savingProxy.value = true;
  proxyFeedback.value = null;
  try {
    const res = await api('/system-settings/proxy', {
      method: 'PUT',
      body: {
        proxy_ip: proxyConfig.value.proxy_ip || null,
        proxy_port: proxyConfig.value.proxy_port,
      },
    });
    proxyConfig.value = {
      proxy_ip: res.proxy_ip || '',
      proxy_port: res.proxy_port,
    };
    const message = '代理配置已保存';
    proxyFeedback.value = {
      type: 'success',
      message,
    };
    toast.success(message);
  } catch (error) {
    const message = resolveErrorMessage(
      error,
      '代理配置保存失败，请检查网络或配置项',
    );
    proxyFeedback.value = {
      type: 'error',
      message,
    };
    toast.error(message);
  } finally {
    savingProxy.value = false;
  }
};

onMounted(() => {
  fetchSettings();
});
</script>

<template>
  <div class="max-w-4xl mx-auto p-6 md:p-8 space-y-8">
    <div class="space-y-1">
      <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
        系统设置
      </h1>
      <p class="text-slate-500 dark:text-slate-400">
        管理全局 AI 模型、视频生成模型和代理网络配置。
      </p>
    </div>

    <div v-if="loading" class="space-y-6">
      <Skeleton class="h-[200px] w-full rounded-xl" />
      <Skeleton class="h-[300px] w-full rounded-xl" />
      <Skeleton class="h-[150px] w-full rounded-xl" />
    </div>

    <div v-else class="space-y-8 pb-12">
      <div
        v-if="pageFeedback"
        :class="[
          'flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-sm',
          getFeedbackClass(pageFeedback.type),
        ]"
      >
        <LucideIcon
          :name="getFeedbackIcon(pageFeedback.type)"
          class="mt-0.5 h-4 w-4 shrink-0"
        />
        <span>{{ pageFeedback.message }}</span>
      </div>

      <!-- AI Config -->
      <Card class="overflow-hidden border-slate-200 dark:border-white/10 shadow-sm transition-all hover:shadow-md">
        <CardHeader class="border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/2">
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <LucideIcon name="Cpu" class="w-5 h-5" />
            </div>
            <div>
              <CardTitle class="text-lg">AI 分析模型配置</CardTitle>
              <CardDescription>用于视频脚本分析、文案创作和对话的核心 AI 模型。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent class="p-6 space-y-6">
          <div class="grid gap-6 md:grid-cols-2">
            <div class="space-y-2">
              <Label>服务商</Label>
              <Select v-model="aiConfig.ai_provider">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="p in aiProviders" :key="p.value" :value="p.value">
                    {{ p.label }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label class="flex items-center justify-between gap-3">
                <span>
                API Key
                <span v-if="aiConfig.ai_api_key_configured" class="text-xs text-green-600 dark:text-green-400 font-normal ml-2">
                  <LucideIcon name="CheckCircle2" class="w-3 h-3 inline mr-1" />
                  {{ aiConfig.ai_api_key_source === 'environment' ? '（来自环境变量）' : '（来自数据库）' }}
                </span>
                </span>
                <button
                  type="button"
                  class="text-xs font-medium text-slate-500 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                  @click="showAiApiKey = !showAiApiKey"
                >
                  {{ showAiApiKey ? '隐藏' : '显示' }}
                </button>
              </Label>
              <Input 
                v-model="aiConfig.ai_api_key" 
                :type="showAiApiKey ? 'text' : 'password'" 
                placeholder="请输入 AI 服务的 API Key"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
            <div class="space-y-2">
              <Label>接口基础地址（可选）</Label>
              <Input 
                v-model="aiConfig.ai_api_base" 
                placeholder="例如：https://api.openai.com/v1"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
            <div class="space-y-2">
              <Label>默认聊天/分析模型</Label>
              <Input 
                v-model="aiConfig.ai_chat_model" 
                placeholder="例如：gpt-4o"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
          </div>
          <div
            v-if="aiFeedback"
            :class="[
              'flex items-start gap-3 rounded-xl border px-4 py-3 text-sm',
              getFeedbackClass(aiFeedback.type),
            ]"
          >
            <LucideIcon
              :name="getFeedbackIcon(aiFeedback.type)"
              class="mt-0.5 h-4 w-4 shrink-0"
            />
            <span>{{ aiFeedback.message }}</span>
          </div>
          <div class="flex justify-end pt-2">
            <Button @click="saveAiSettings" :disabled="savingAi" class="min-w-[100px]">
              <LucideIcon v-if="savingAi" name="Loader2" class="w-4 h-4 mr-2 animate-spin" />
              {{ savingAi ? '保存 AI 配置中...' : '保存 AI 配置' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- Video Config -->
      <Card class="overflow-hidden border-slate-200 dark:border-white/10 shadow-sm transition-all hover:shadow-md">
        <CardHeader class="border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/2">
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <LucideIcon name="Video" class="w-5 h-5" />
            </div>
            <div>
              <CardTitle class="text-lg">AI 视频模型配置</CardTitle>
              <CardDescription>用于生成视频分镜、参考图和视频素材的生成式模型。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent class="p-6 space-y-6">
          <div class="grid gap-6 md:grid-cols-2">
            <div class="space-y-2">
              <Label>服务商</Label>
              <Select v-model="videoConfig.video_provider">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="p in videoProviders" :key="p.value" :value="p.value">
                    {{ p.label }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label class="flex items-center justify-between gap-3">
                <span>
                API Key
                <span v-if="videoConfig.video_api_key_configured" class="text-xs text-green-600 dark:text-green-400 font-normal ml-2">
                  <LucideIcon name="CheckCircle2" class="w-3 h-3 inline mr-1" />
                  {{ videoConfig.video_api_key_source === 'environment' ? '（来自环境变量）' : '（来自数据库）' }}
                </span>
                </span>
                <button
                  type="button"
                  class="text-xs font-medium text-slate-500 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                  @click="showVideoApiKey = !showVideoApiKey"
                >
                  {{ showVideoApiKey ? '隐藏' : '显示' }}
                </button>
              </Label>
              <Input 
                v-model="videoConfig.video_api_key" 
                :type="showVideoApiKey ? 'text' : 'password'" 
                placeholder="请输入视频服务的 API Key"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
            <div class="space-y-2">
              <Label>接口基础地址（可选）</Label>
              <Input 
                v-model="videoConfig.video_api_base" 
                :placeholder="videoApiBasePlaceholder"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
            <div class="space-y-2">
              <Label>默认视频模型</Label>
              <Input 
                v-model="videoConfig.video_model" 
                :placeholder="videoModelPlaceholder"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
          </div>

          <div
            class="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm leading-6 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
          >
            <div class="font-medium text-slate-900 dark:text-white">
              视频接口说明
            </div>
            <div class="mt-1">
              {{ videoProviderDescription }}
            </div>
          </div>
          
          <div class="grid gap-6 md:grid-cols-2">
            <div class="space-y-2">
              <Label>图生视频模型</Label>
              <Input 
                v-model="videoConfig.video_image_to_video_model" 
                placeholder="留空时回退到默认视频模型"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
            <div class="space-y-2">
              <Label>文生视频模型</Label>
              <Input 
                v-model="videoConfig.video_text_to_video_model" 
                placeholder="留空时回退到默认视频模型"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
          </div>
          <div
            v-if="videoFeedback"
            :class="[
              'flex items-start gap-3 rounded-xl border px-4 py-3 text-sm',
              getFeedbackClass(videoFeedback.type),
            ]"
          >
            <LucideIcon
              :name="getFeedbackIcon(videoFeedback.type)"
              class="mt-0.5 h-4 w-4 shrink-0"
            />
            <span>{{ videoFeedback.message }}</span>
          </div>

          <div class="flex justify-end pt-2">
            <Button @click="saveVideoSettings" :disabled="savingVideo" class="min-w-[100px] bg-purple-600 hover:bg-purple-700 text-white">
              <LucideIcon v-if="savingVideo" name="Loader2" class="w-4 h-4 mr-2 animate-spin" />
              {{ savingVideo ? '保存视频配置中...' : '保存视频配置' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- Proxy Config -->
      <Card class="overflow-hidden border-slate-200 dark:border-white/10 shadow-sm transition-all hover:shadow-md">
        <CardHeader class="border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/2">
          <div class="flex items-center gap-3">
            <div class="p-2 rounded-lg bg-orange-50 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400">
              <LucideIcon name="Globe" class="w-5 h-5" />
            </div>
            <div>
              <CardTitle class="text-lg">代理网络配置</CardTitle>
              <CardDescription>配置系统访问海外平台（如 TikTok）时使用的 HTTP 代理。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent class="p-6 space-y-6">
          <div class="grid gap-6 md:grid-cols-3">
            <div class="md:col-span-2 space-y-2">
              <Label>代理服务器地址</Label>
              <Input 
                v-model="proxyConfig.proxy_ip" 
                placeholder="例如：127.0.0.1"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
            <div class="space-y-2">
              <Label>代理端口</Label>
              <Input 
                v-model.number="proxyConfig.proxy_port" 
                type="number"
                placeholder="例如：7890"
                class="bg-slate-50/50 dark:bg-black/20"
              />
            </div>
          </div>
          <div
            v-if="proxyFeedback"
            :class="[
              'flex items-start gap-3 rounded-xl border px-4 py-3 text-sm',
              getFeedbackClass(proxyFeedback.type),
            ]"
          >
            <LucideIcon
              :name="getFeedbackIcon(proxyFeedback.type)"
              class="mt-0.5 h-4 w-4 shrink-0"
            />
            <span>{{ proxyFeedback.message }}</span>
          </div>
          <div class="flex justify-end pt-2">
            <Button @click="saveProxySettings" :disabled="savingProxy" class="min-w-[100px] bg-orange-600 hover:bg-orange-700 text-white">
              <LucideIcon v-if="savingProxy" name="Loader2" class="w-4 h-4 mr-2 animate-spin" />
              {{ savingProxy ? '保存代理配置中...' : '保存代理配置' }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<style scoped>
/* Optional styling */
</style>
