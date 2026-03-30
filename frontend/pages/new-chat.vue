<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import InputPromptModal from "~/components/custom/InputPromptModal.vue";
import ConfirmModal from "~/components/custom/ConfirmModal.vue";

import TaskTimeline from "~/components/custom/TaskTimeline.vue";

definePageMeta({
  layout: "console",
  middleware: "auth",
  ssr: false,
});

const { t } = useI18n();
const api = useOmniSellApi();
const auth = useAuth();
const route = useRoute();
const router = useRouter();
const runtimeConfig = useRuntimeConfig();
const chatStore = useChatStore();

useHead({
  title: computed(() => t("video.analysis.pageTitle")),
});

type ModeTab = "script" | "remake" | "create";
type ProjectWorkflowType = "analysis" | "create" | "remake";

interface ProjectListItem {
  id: number;
  title: string;
  source_url: string;
  source_platform: string;
  workflow_type: ProjectWorkflowType;
  source_type: "url" | "upload";
  source_name: string;
  status: string;
  media_url: string | null;
  objective: string;
  summary: string;
  created_at: string;
  updated_at: string;
}

interface ProjectTaskStep {
  id: number;
  step_key: string;
  title: string;
  detail: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  error_detail: string | null;
  display_order: number;
  updated_at: string;
}

interface ProjectVideoGeneration {
  status: string;
  provider: string | null;
  model: string | null;
  objective: string | null;
  asset_type: string | null;
  asset_name: string | null;
  asset_url: string | null;
  audio_name: string | null;
  audio_url: string | null;
  reference_frames: string[];
  script: string | null;
  storyboard: string | null;
  prompt: string | null;
  provider_task_id: string | null;
  result_video_url: string | null;
  error_detail: string | null;
  updated_at: string | null;
}

interface ProjectSourceVisualFeatures {
  orientation: string | null;
  resolution: string | null;
  frame_rate: string | null;
  keyframe_count: number;
  shot_density: string | null;
  scene_pace: string | null;
  lighting: string | null;
  contrast: string | null;
  saturation: string | null;
  color_temperature: string | null;
  framing_focus: string | null;
  camera_motion: string | null;
  dominant_palette: string[];
  summary: string | null;
}

interface ProjectSourceAnalysis {
  reference_frames: string[];
  visual_features: ProjectSourceVisualFeatures | null;
}

interface ProjectDetail extends ProjectListItem {
  script_overview: {
    full_text: string;
    dialogue_text: string;
    narration_text: string;
    caption_text: string;
  };
  ecommerce_analysis: {
    title: string;
    content: string | null;
  };
  source_analysis: ProjectSourceAnalysis;
  timeline_segments: Array<{
    id: number;
    segment_type: string;
    speaker: string | null;
    start_ms: number;
    end_ms: number;
    content: string;
  }>;
  video_generation: ProjectVideoGeneration;
  task_steps: ProjectTaskStep[];
}

interface AssistantFeedback {
  status: "pending" | "error";
  objective: string;
  sourceLabel: string;
  message: string;
}

interface RemakeAdviceCard {
  title: string;
  body: string;
}

interface RemakeScriptCard {
  title: string;
  timing: string;
  voiceover: string;
  subtitle: string;
  direction: string;
}

const activeMode = ref<ModeTab>("script");
const inputText = ref("");
const sending = ref(false);
const retryingAiAnalysis = ref(false);
const loadingDetail = ref(false);
const errorMessage = ref("");
const assistantFeedback = ref<AssistantFeedback | null>(null);
const selectedFile = ref<File | null>(null);
const selectedAudioFile = ref<File | null>(null);
const selectedUrls = ref<string[]>([]);
const projects = chatStore.projects;
const loadingHistory = chatStore.loadingHistory;
const selectedProject = chatStore.selectedProject;
const fileInputRef = ref<HTMLInputElement | null>(null);
const audioInputRef = ref<HTMLInputElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const isUserClearedMode = ref(false);

const showFilePopover = ref(false);
const showLinkModal = ref(false);
const linkDraft = ref("");
const linkModalError = ref("");
const renamingProjectId = ref<number | null>(null);
const renameDraft = ref("");
const renameModalError = ref("");
const renamingProjectPending = ref(false);
const deletingProjectId = ref<number | null>(null);
const showVideoDetailModal = ref(false);
const activeDetailTab = ref<"analysis" | "timeline" | "generation">("analysis");

const imageFileExtensions = [".jpg", ".jpeg", ".png", ".webp"];
const videoFileExtensions = [
  ".mp4",
  ".mov",
  ".mkv",
  ".webm",
  ".avi",
  ".m4v",
  ".mpeg",
  ".mpg",
];
const audioFileExtensions = [
  ".aac",
  ".flac",
  ".m4a",
  ".mp3",
  ".ogg",
  ".wav",
  ".webm",
];
const sourceVideoAccept = "video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v,.mpeg,.mpg";
const productAssetAccept =
  "image/*,.jpg,.jpeg,.png,.webp,video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v,.mpeg,.mpg";
const remakeAudioAccept = "audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg,.webm";

const hasFileExtension = (filename: string, extensions: string[]) => {
  const lowerName = filename.toLowerCase();
  return extensions.some((extension) => lowerName.endsWith(extension));
};

const isImageFile = (file: { name: string; type?: string | null }) =>
  (file.type || "").startsWith("image/") ||
  hasFileExtension(file.name, imageFileExtensions);

const isVideoFile = (file: { name: string; type?: string | null }) =>
  (file.type || "").startsWith("video/") ||
  hasFileExtension(file.name, videoFileExtensions);

const isAudioFile = (file: { name: string; type?: string | null }) =>
  (file.type || "").startsWith("audio/") ||
  hasFileExtension(file.name, audioFileExtensions);

const toggleFilePopover = () => {
  showFilePopover.value = !showFilePopover.value;
};

const hideFilePopover = () => {
  showFilePopover.value = false;
};

const handleAddLinkClick = () => {
  if (activeMode.value === "remake" && selectedProject.value) {
    errorMessage.value =
      "视频复刻会直接使用当前项目作为对标视频。你可以直接生成万相复刻视频，也可以额外上传产品图或产品视频来锁定素材外观。";
    return;
  }
  hideFilePopover();
  linkDraft.value = detectedUrl.value || "https://";
  linkModalError.value = "";
  showLinkModal.value = true;
};

const closeLinkModal = () => {
  showLinkModal.value = false;
  linkModalError.value = "";
};

const upsertDetectedUrl = (url: string) => {
  if (!selectedUrls.value.includes(url)) {
    selectedUrls.value.push(url);
  }
  // 从输入框中移除 URL
  inputText.value = inputText.value.replace(url, "").trim();
};

const confirmLinkModal = () => {
  const value = linkDraft.value.trim();

  if (!value) {
    linkModalError.value = "请输入视频链接";
    return;
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    linkModalError.value = "请输入有效的 http 或 https 链接";
    return;
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    linkModalError.value = "仅支持 http 或 https 链接";
    return;
  }

  selectedFile.value = null;
  upsertDetectedUrl(parsed.toString());
  closeLinkModal();
  void focusTextarea();
};

const modePrefills: Record<ModeTab, () => string> = {
  script: () =>
    "从这个视频中提取完整的文本脚本，包括对话、旁白以及所有文字字幕：",
  remake: () => "复刻这个视频的画面细节，包括画面构图、色彩、光影等：",
  create: () =>
    `我希望创作的视频类型：[UGC种草/产品口播/产品演示/痛点-解决/前后对比/反应展示/故事讲述]
我的目标客群：[种族/地区/职业/生理特征等]
我的商品名称：
我的商品卖点：
我倾向的视频风格：`,
};

const copy = computed(() => ({
  heroTitle: t("video.analysis.heroTitle"),
  tabScript: "分析脚本",
  tabRemake: "复刻爆款",
  tabCreate: "创作爆款",
  inputPlaceholder: "输入你想让 AI 帮忙的指令，或者粘贴链接...",
  chatHistory: "历史对话",
  detectedLink: "检测到链接",
}));

const modeToWorkflowType = (mode: ModeTab): ProjectWorkflowType =>
  mode === "create" ? "create" : mode === "remake" ? "remake" : "analysis";

const workflowTypeToMode = (workflowType: ProjectWorkflowType): ModeTab =>
  workflowType === "create"
    ? "create"
    : workflowType === "remake"
      ? "remake"
      : "script";

const currentRouteMode = computed<ModeTab>(() => {
  if (route.path.startsWith("/creation")) {
    return "create";
  }
  if (route.path.startsWith("/repurpose")) {
    return "remake";
  }
  return "script";
});

const getModePrefill = (mode: ModeTab) => modePrefills[mode]();
inputText.value = getModePrefill(activeMode.value);

const extractFirstUrl = (value: string): string | null => {
  const match = value.match(/https?:\/\/[^\s]+/i);
  if (!match) return null;
  return match[0].replace(/[),.;!?]+$/, "");
};

const getBackendOrigin = () => {
  const fallbackOrigin = import.meta.client
    ? window.location.origin
    : "http://127.0.0.1:8000";
  const apiBase = (runtimeConfig.public.apiBase || "").trim();
  if (!apiBase) {
    return fallbackOrigin;
  }
  try {
    return new URL(apiBase, fallbackOrigin).origin;
  } catch {
    return fallbackOrigin;
  }
};

const resolveAssetUrl = (value: string | null | undefined): string | null => {
  const normalized = (value || "").trim();
  if (!normalized || normalized.startsWith("upload://")) {
    return null;
  }
  if (/^(https?:|data:|blob:)/i.test(normalized)) {
    return normalized;
  }
  try {
    return new URL(normalized, `${getBackendOrigin()}/`).toString();
  } catch {
    return normalized;
  }
};

const isDirectPreviewableUrl = (value: string | null | undefined) => {
  const normalized = (value || "").trim().toLowerCase();
  if (!normalized || normalized.startsWith("upload://")) {
    return false;
  }
  return !normalized.includes("tiktok.com") && !normalized.includes("douyin.com");
};

const detectedUrl = computed(() => extractFirstUrl(inputText.value));

// 监听 detectedUrl 变化，自动添加到 selectedUrls
watch(detectedUrl, (url, oldUrl) => {
  if (url && url !== oldUrl && !selectedUrls.value.includes(url)) {
    selectedUrls.value.push(url);
    // 使用 nextTick 避免循环
    nextTick(() => {
      inputText.value = inputText.value.replace(url, "").trim();
    });
  }
});

const hasObjective = computed(() => inputText.value.trim().length >= 2);
const remakeGeneration = computed(
  () => selectedProject.value?.video_generation || null,
);
const sourceAnalysis = computed(
  () => selectedProject.value?.source_analysis || null,
);
const sourceReferenceFrames = computed(
  () =>
    (sourceAnalysis.value?.reference_frames || [])
      .map((frame) => resolveAssetUrl(frame))
      .filter((frame): frame is string => Boolean(frame)),
);
const sourceVisualFeatures = computed(
  () => sourceAnalysis.value?.visual_features || null,
);
const hasVisibleSourceAnalysis = computed(() => {
  const visual = sourceVisualFeatures.value;
  return Boolean(
    sourceReferenceFrames.value.length > 0 ||
      visual?.summary ||
      visual?.dominant_palette?.length ||
      visual?.scene_pace ||
      visual?.lighting ||
      visual?.camera_motion,
  );
});
const sourceVisualMetaBadges = computed(() => {
  const visual = sourceVisualFeatures.value;
  if (!visual) {
    return [];
  }
  return [
    { label: "画幅", value: visual.orientation || "" },
    { label: "分辨率", value: visual.resolution || "" },
    { label: "帧率", value: visual.frame_rate || "" },
    {
      label: "关键帧",
      value: visual.keyframe_count ? `${visual.keyframe_count} 帧` : "",
    },
  ].filter((item) => item.value);
});
const sourceVisualSignalCards = computed(() => {
  const visual = sourceVisualFeatures.value;
  if (!visual) {
    return [];
  }
  return [
    { label: "镜头节奏", value: visual.scene_pace || "" },
    { label: "布光", value: visual.lighting || "" },
    { label: "对比度", value: visual.contrast || "" },
    { label: "饱和度", value: visual.saturation || "" },
    { label: "色温", value: visual.color_temperature || "" },
    { label: "构图焦点", value: visual.framing_focus || "" },
    { label: "运镜方式", value: visual.camera_motion || "" },
    { label: "镜头密度", value: visual.shot_density || "" },
  ].filter((item) => item.value);
});
const remakeReferenceFrames = computed(
  () =>
    (remakeGeneration.value?.reference_frames || [])
      .map((frame) => resolveAssetUrl(frame))
      .filter((frame): frame is string => Boolean(frame)),
);
const selectedProjectMediaUrl = computed(() =>
  resolveAssetUrl(selectedProject.value?.media_url),
);
const selectedProjectSourcePageUrl = computed(() => {
  if (selectedProject.value?.source_type !== "url") {
    return null;
  }
  return resolveAssetUrl(selectedProject.value?.source_url);
});
const selectedProjectPreviewUrl = computed(() => {
  if (selectedProjectMediaUrl.value) {
    return selectedProjectMediaUrl.value;
  }
  const sourceUrl = selectedProject.value?.source_url || null;
  if (!isDirectPreviewableUrl(sourceUrl)) {
    return null;
  }
  return resolveAssetUrl(sourceUrl);
});
const remakeAudioUrl = computed(() =>
  resolveAssetUrl(remakeGeneration.value?.audio_url),
);
const remakeResultVideoUrl = computed(() =>
  resolveAssetUrl(remakeGeneration.value?.result_video_url),
);
const isRemakeSubmission = computed(
  () => activeMode.value === "remake" && Boolean(selectedProject.value),
);
const hasSavedRemakeAsset = computed(() =>
  Boolean(remakeGeneration.value?.asset_url),
);
const hasSavedRemakeAudio = computed(() =>
  Boolean(remakeGeneration.value?.audio_url),
);
const hasVisibleRemakeGeneration = computed(() => {
  const generation = remakeGeneration.value;
  return Boolean(
    generation &&
    (generation.status !== "idle" ||
      generation.asset_name ||
      generation.audio_name ||
      generation.result_video_url ||
      generation.error_detail ||
      generation.script ||
      generation.storyboard ||
      generation.prompt ||
      generation.reference_frames.length > 0),
  );
});
const currentUploadAccept = computed(() =>
  isRemakeSubmission.value ? productAssetAccept : sourceVideoAccept,
);
const uploadButtonLabel = computed(() =>
  isRemakeSubmission.value ? "上传产品图/视频" : "上传视频",
);
const hasNewSourceSelection = computed(
  () => selectedFile.value !== null || selectedUrls.value.length > 0,
);
const canSend = computed(() => {
  if (sending.value) {
    return false;
  }

  if (isRemakeSubmission.value) {
    return (
      selectedProject.value?.status === "ready" &&
      (inputText.value.trim().length === 0 ||
        inputText.value.trim().length >= 2)
    );
  }

  return (
    hasObjective.value &&
    Boolean(hasNewSourceSelection.value || selectedProject.value)
  );
});
const projectsForCurrentMode = computed(() => projects.value);
const hasConversation = computed(() =>
  Boolean(selectedProject.value || assistantFeedback.value),
);
const activeConversationObjective = computed(
  () =>
    assistantFeedback.value?.objective ||
    (activeMode.value === "remake"
      ? selectedProject.value?.video_generation?.objective ||
        "请基于这个对标视频生成一条适配我产品的视频"
      : selectedProject.value?.objective || "") ||
    "",
);
const ecommerceAnalysisContent = computed(
  () => selectedProject.value?.ecommerce_analysis?.content?.trim() || "",
);
const ecommerceAnalysisLooksFailed = computed(() => {
  const analysis = ecommerceAnalysisContent.value;
  if (!analysis) {
    return false;
  }
  return (
    analysis.startsWith("AI 分析失败：") ||
    analysis.includes("无法进行 AI 分析")
  );
});
const getDefaultAnalysisTitle = (workflowType?: ProjectWorkflowType) => {
  if (workflowType === "remake") {
    return "TikTok Remake Engine 复刻方案";
  }
  return "TikTok 电商效果深度分析";
};
const analysisPanelTitle = computed(() =>
  selectedProject.value?.ecommerce_analysis?.title ||
  getDefaultAnalysisTitle(selectedProject.value?.workflow_type),
);
const analysisRetryLabel = computed(() =>
  selectedProject.value?.workflow_type === "remake"
    ? "重试复刻方案"
    : "重试深度分析",
);
const analysisEmptyReadyMessage = computed(() =>
  selectedProject.value?.workflow_type === "remake"
    ? "当前还没有复刻方案结果。你可以点击右上角重试按钮重新生成一版文本方案。"
    : "当前还没有 TikTok 电商效果深度分析结果。你可以点击右上角重试按钮单独触发一次。",
);
const analysisEmptyProcessingMessage = computed(() =>
  selectedProject.value?.workflow_type === "remake"
    ? "当前任务仍在处理中，复刻建议、AI 文案脚本和视频生成方案会在前置任务完成后自动生成。"
    : "当前任务仍在处理中，TikTok 电商效果深度分析会在前置任务完成后自动生成。",
);

const asRecord = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
};

const asString = (value: unknown): string =>
  typeof value === "string" ? value.trim() : "";

const asStringList = (value: unknown, limit = Number.MAX_SAFE_INTEGER) => {
  if (!Array.isArray(value)) {
    return [] as string[];
  }
  return value
    .map((item) => asString(item))
    .filter(Boolean)
    .slice(0, limit);
};

const joinNonEmpty = (
  values: Array<string | null | undefined>,
  separator = "；",
) =>
  values
    .map((value) => (value || "").trim())
    .filter(Boolean)
    .join(separator);

const formatSecondsLabel = (value: unknown) => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "";
  }
  return `${value < 10 ? value.toFixed(1) : value.toFixed(0)}s`;
};

const formatSecondRange = (start: unknown, end: unknown) => {
  const startLabel = formatSecondsLabel(start);
  const endLabel = formatSecondsLabel(end);
  if (!startLabel && !endLabel) {
    return "";
  }
  if (!endLabel) {
    return startLabel;
  }
  if (!startLabel) {
    return endLabel;
  }
  return `${startLabel} - ${endLabel}`;
};

const buildStageVoiceover = (
  stage: string,
  keyContent: string,
  userGoal: string,
  ctaHint: string,
) => {
  if (stage.includes("Hook")) {
    return `先别铺垫，开场直接抛出结果或冲突点：${keyContent || userGoal}`;
  }
  if (stage.includes("展示")) {
    return `紧接着用产品细节或演示动作把重点讲清楚：${keyContent || userGoal}`;
  }
  if (stage.includes("转折")) {
    return `这里补一刀证据、对比或结果画面，强化用户相信的理由：${keyContent || userGoal}`;
  }
  return `最后直接收口并给动作指令：${ctaHint || keyContent || userGoal}`;
};

const parsedRemakeAnalysis = computed<Record<string, unknown> | null>(() => {
  if (
    selectedProject.value?.workflow_type !== "remake" ||
    ecommerceAnalysisLooksFailed.value
  ) {
    return null;
  }

  const raw = ecommerceAnalysisContent.value;
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return null;
  }

  return null;
});

const hasStructuredRemakeAnalysis = computed(() =>
  Boolean(parsedRemakeAnalysis.value),
);

const remakeAnalysisSummary = computed(() => {
  const payload = parsedRemakeAnalysis.value;
  if (!payload) {
    return "";
  }
  const contentStrategy = asRecord(payload.content_strategy);
  const visual = asRecord(payload.visual);
  const replicableParameters = asStringList(visual.replicable_parameters, 1);
  return (
    asString(contentStrategy.carrier_summary) ||
    replicableParameters[0] ||
    selectedProject.value?.summary ||
    ""
  );
});

const remakeAdviceCards = computed<RemakeAdviceCard[]>(() => {
  const payload = parsedRemakeAnalysis.value;
  if (!payload) {
    return [];
  }

  const visual = asRecord(payload.visual);
  const composition = asRecord(visual.composition);
  const lighting = asRecord(visual.lighting);
  const color = asRecord(visual.color);
  const viralLogic = asRecord(payload.viral_logic);
  const contentStrategy = asRecord(payload.content_strategy);
  const executionPlan = asRecord(payload.execution_plan);

  const visualizedSellingPoints = Array.isArray(
    contentStrategy.visualized_selling_points,
  )
    ? contentStrategy.visualized_selling_points
        .map((item) => {
          const record = asRecord(item);
          return joinNonEmpty(
            [
              asString(record.selling_point),
              asString(record.visual_expression),
            ],
            "：",
          );
        })
        .filter(Boolean)
        .slice(0, 2)
        .join("；")
    : "";

  const shootingPreparation = asStringList(
    executionPlan.shooting_preparation,
    2,
  ).join("；");
  const postProduction = asStringList(executionPlan.post_production, 2).join(
    "；",
  );
  const publishingStrategy = asStringList(
    executionPlan.publishing_strategy,
    1,
  )[0];

  return [
    {
      title: "画面构图",
      body: joinNonEmpty([
        asString(composition.subject_position),
        asString(composition.product_focus),
      ]),
    },
    {
      title: "光影与色彩",
      body: joinNonEmpty([
        asString(lighting.key_light),
        asString(color.palette),
        asString(color.contrast),
      ]),
    },
    {
      title: "开场钩子",
      body: joinNonEmpty([
        asString(viralLogic.hook_type)
          ? `${asString(viralLogic.hook_type)}型开场`
          : "",
        asString(viralLogic.hook_reason),
      ]),
    },
    {
      title: "卖点表达",
      body: joinNonEmpty([
        visualizedSellingPoints,
        asString(contentStrategy.carrier_summary),
      ]),
    },
    {
      title: "拍摄执行",
      body: shootingPreparation,
    },
    {
      title: "剪辑发布",
      body: joinNonEmpty([postProduction, publishingStrategy]),
    },
  ].filter((card) => card.body);
});

const remakeScriptCards = computed<RemakeScriptCard[]>(() => {
  const payload = parsedRemakeAnalysis.value;
  if (!payload) {
    return [];
  }

  const timeline = Array.isArray(payload.timeline) ? payload.timeline : [];
  const viralLogic = asRecord(payload.viral_logic);
  const ctaHint =
    (Array.isArray(viralLogic.interaction_mechanisms)
      ? viralLogic.interaction_mechanisms
          .map((item) => asString(asRecord(item).execution))
          .find(Boolean)
      : "") || "";

  return timeline
    .map((item, index) => {
      const record = asRecord(item);
      const stage = asString(record.stage) || `段落 ${index + 1}`;
      const keyContent = asString(record.key_content);
      const userGoal = asString(record.user_psychology_goal);
      const editingDirection = asString(record.editing_direction);
      const subtitle =
        (index === timeline.length - 1 ? ctaHint : "") ||
        keyContent ||
        userGoal ||
        "补一句大字幕强化重点";

      return {
        title: stage,
        timing: formatSecondRange(record.start_s, record.end_s),
        voiceover: buildStageVoiceover(stage, keyContent, userGoal, ctaHint),
        subtitle,
        direction: editingDirection || userGoal || "按原片节奏推进镜头",
      };
    })
    .filter((item) => item.voiceover || item.subtitle || item.direction);
});

const remakeWanxiangPrompt = computed(() => {
  const payload = parsedRemakeAnalysis.value;
  if (!payload) {
    return "";
  }

  const visual = asRecord(payload.visual);
  const color = asRecord(visual.color);
  const cameraMotion = asRecord(visual.camera_motion);
  const timeline = Array.isArray(payload.timeline) ? payload.timeline : [];
  const opening = timeline.length
    ? asString(asRecord(timeline[0]).key_content)
    : "";
  const ending = timeline.length
    ? asString(asRecord(timeline[timeline.length - 1]).key_content)
    : "";

  return joinNonEmpty(
    [
      `竖屏 ${asString(visual.aspect_ratio) || "9:16"} 电商短视频，复刻对标视频的镜头节奏、构图和商品展示方式`,
      asString(color.palette),
      asString(cameraMotion.body),
      opening ? `开场重点：${opening}` : "",
      ending ? `结尾动作：${ending}` : "",
      activeConversationObjective.value
        ? `目标：${activeConversationObjective.value}`
        : "",
    ],
    "。 ",
  );
});

const remakeWanxiangNotes = computed(() => {
  const notes = [
    remakeGeneration.value?.status === "processing" ||
    remakeGeneration.value?.status === "ready"
      ? "当前复刻流程会直接调用通义万相 / DashScope 生成视频结果。"
      : "提交复刻后会直接调用通义万相 / DashScope；上传产品图或产品视频时更适合锁定产品外观，不上传素材时会按脚本文生视频。",
    "如果你要更像原片，优先保留竖屏 9:16、前 3 秒大字幕和快节奏切镜。",
  ];

  if (remakeGeneration.value?.asset_type === "text") {
    notes.push("当前这次没有上传产品素材，系统已经按 AI 文案脚本直接生成。");
  }

  return notes.filter(Boolean);
});

let projectPollingTimer: ReturnType<typeof setInterval> | null = null;

const clearProjectPollingTimer = () => {
  if (projectPollingTimer) {
    clearInterval(projectPollingTimer);
    projectPollingTimer = null;
  }
};

onUnmounted(() => {
  clearProjectPollingTimer();
});

const pipelineTasks = computed(() => selectedProject.value?.task_steps || []);
const currentWorkflowLabel = computed(() => {
  if (
    pipelineTasks.value.some(
      (task) => task.step_key === "prepare_reference_asset",
    )
  ) {
    return "视频复刻工作流";
  }
  if (selectedProject.value?.workflow_type === "create") {
    return "创作爆款工作流";
  }
  if (selectedProject.value?.workflow_type === "remake") {
    return "复刻爆款工作流";
  }
  return "视频分析工作流";
});
const totalTaskCount = computed(() => pipelineTasks.value.length);
const completedTaskCount = computed(
  () =>
    pipelineTasks.value.filter((task) => task.status === "completed").length,
);
const failedTask = computed(
  () => pipelineTasks.value.find((task) => task.status === "failed") || null,
);
const pipelineExpanded = ref(true);
const pipelineSummary = computed(() => {
  if (!selectedProject.value || totalTaskCount.value === 0) {
    return "";
  }
  if (selectedProject.value.status === "ready") {
    return `${currentWorkflowLabel.value}已完成 (${completedTaskCount.value}/${totalTaskCount.value})`;
  }
  if (selectedProject.value.status === "failed") {
    return `${currentWorkflowLabel.value}失败 (${completedTaskCount.value}/${totalTaskCount.value})`;
  }
  return `${currentWorkflowLabel.value}执行中 (${completedTaskCount.value}/${totalTaskCount.value})`;
});

const currentPendingTaskStep = computed(() => {
  return (
    pipelineTasks.value.find((task) => task.status === "in_progress") ||
    pipelineTasks.value.find((task) => task.status === "pending") ||
    null
  );
});

const processingStatusMessage = computed(() => {
  if (!selectedProject.value || selectedProject.value.status === "ready") {
    return "";
  }

  const messageParts = ["当前项目还在处理中。"];
  const pendingTask = currentPendingTaskStep.value;
  if (pendingTask?.title) {
    messageParts.push(`未完成步骤：${pendingTask.title}。`);
  }
  if (pendingTask?.detail) {
    messageParts.push(`${pendingTask.detail}`);
  }

  const summary = (selectedProject.value.summary || "").trim();
  if (
    summary &&
    summary !== pendingTask?.detail &&
    summary !== pendingTask?.title &&
    !messageParts.some((item) => item.includes(summary))
  ) {
    messageParts.push(`当前进度：${summary}`);
  }

  return messageParts.join(" ").trim();
});

const analysisProcessingMessage = computed(() => {
  if (processingStatusMessage.value) {
    return processingStatusMessage.value;
  }
  return selectedProject.value?.workflow_type === "remake"
    ? "当前任务仍在处理中，复刻建议、AI 文案脚本和视频生成方案会在前置任务完成后自动生成。"
    : "当前任务仍在处理中，TikTok 电商效果深度分析会在前置任务完成后自动生成。";
});

const selectedSourceCard = computed(() => {
  if (selectedUrls.value.length > 0) {
    return selectedUrls.value.map((url) => ({
      key: url,
      title: "Video",
      subtitle: url,
      icon: "Video" as const,
      dismissible: true,
      clearKey: url,
    }));
  }

  const cards: Array<{
    key: string;
    title: string;
    subtitle: string;
    icon: "Image" | "Video" | "Music";
    dismissible: boolean;
    clearKey: string | null;
  }> = [];

  if (selectedFile.value) {
    const isRemakeAsset = isRemakeSubmission.value;
    const isImageAsset = isImageFile(selectedFile.value);
    cards.push({
      key: "selected_asset",
      title: isRemakeAsset
        ? isImageAsset
          ? "产品图"
          : "产品视频"
        : selectedFile.value.name,
      subtitle: isRemakeAsset ? "用于视频复刻" : "本地文件",
      icon:
        isRemakeAsset && isImageAsset
          ? ("Image" as const)
          : ("Video" as const),
      dismissible: true,
      clearKey: "selected_asset",
    });
  } else if (isRemakeSubmission.value && remakeGeneration.value?.asset_name) {
    cards.push({
      key: "saved_asset",
      title:
        remakeGeneration.value.asset_type === "image"
          ? "已保存产品图"
          : "已保存产品视频",
      subtitle: remakeGeneration.value.asset_name,
      icon:
        remakeGeneration.value.asset_type === "image"
          ? ("Image" as const)
          : ("Video" as const),
      dismissible: true,
      clearKey: "remake_asset",
    });
  }

  if (isRemakeSubmission.value && selectedAudioFile.value) {
    cards.push({
      key: "selected_audio",
      title: "配音音频",
      subtitle: selectedAudioFile.value.name,
      icon: "Music",
      dismissible: true,
      clearKey: "selected_audio",
    });
  } else if (isRemakeSubmission.value && remakeGeneration.value?.audio_name) {
    cards.push({
      key: "saved_audio",
      title: "已保存配音",
      subtitle: remakeGeneration.value.audio_name,
      icon: "Music",
      dismissible: false,
      clearKey: null,
    });
  }

  return cards;
});

const clearSelectedSource = (clearKey?: string | null) => {
  if (clearKey === "remake_asset") {
    resetComposer();
    return;
  }

  if (clearKey === "selected_asset") {
    selectedFile.value = null;
    if (fileInputRef.value) {
      fileInputRef.value.value = "";
    }
    return;
  }

  if (clearKey === "selected_audio") {
    selectedAudioFile.value = null;
    if (audioInputRef.value) {
      audioInputRef.value.value = "";
    }
    return;
  }

  if (clearKey) {
    selectedUrls.value = selectedUrls.value.filter(
      (url) => url !== clearKey,
    );
    return;
  }
};

const formatRange = (startMs: number, endMs: number) =>
  `${(startMs / 1000).toFixed(1)}s - ${(endMs / 1000).toFixed(1)}s`;

const formatPlatformLabel = (value: string) => {
  const labels: Record<string, string> = {
    bilibili: "Bilibili",
    douyin: "Douyin",
    generic: "Web Video",
    instagram: "Instagram",
    local_upload: "Local Upload",
    tiktok: "TikTok",
    xiaohongshu: "小红书",
    youtube: "YouTube",
  };
  return labels[value] || value;
};

const formatProjectSource = (project: ProjectListItem | ProjectDetail) =>
  project.source_type === "upload"
    ? `文件 · ${project.source_name}`
    : `${formatPlatformLabel(project.source_platform)} · ${project.source_name}`;

const extractErrorMessage = (error: unknown, fallback: string) => {
  if (error && typeof error === "object") {
    const detail = (error as { data?: { detail?: string } }).data?.detail;
    if (typeof detail === "string" && detail) return detail;
    const message = (error as { message?: string }).message;
    if (typeof message === "string" && message) return message;
  }
  return fallback;
};

const buildProjectTitle = (mode: ModeTab, sourceLabel: string) => {
  const modeLabel: Record<ModeTab, string> = {
    script: copy.value.tabScript,
    remake: copy.value.tabRemake,
    create: copy.value.tabCreate,
  };
  return `${modeLabel[mode]} · ${sourceLabel}`.slice(0, 120);
};

const resizeTextarea = () => {
  const textarea = textareaRef.value;
  if (!textarea) {
    return;
  }

  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
};

const focusTextarea = async () => {
  await nextTick();
  if (textareaRef.value) {
    textareaRef.value.focus();
  }
};

watch(
  inputText,
  async () => {
    await nextTick();
    resizeTextarea();
  },
  { immediate: true },
);

const resetComposer = () => {
  // HIDDEN by default for new chats to keep it truly clean and "no selection" feel
  isUserClearedMode.value = true;
  inputText.value = "";
  selectedFile.value = null;
  selectedAudioFile.value = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
  if (audioInputRef.value) {
    audioInputRef.value.value = "";
  }
  selectedUrls.value = [];
  selectedProject.value = null;
  assistantFeedback.value = null;
  errorMessage.value = "";
  pipelineExpanded.value = true;
};

const toProjectListItem = (project: ProjectDetail): ProjectListItem => ({
  id: project.id,
  title: project.title,
  source_url: project.source_url,
  source_platform: project.source_platform,
  workflow_type: project.workflow_type,
  source_type: project.source_type,
  source_name: project.source_name,
  status: project.status,
  media_url: project.media_url,
  objective: project.objective,
  summary: project.summary,
  created_at: project.created_at,
  updated_at: project.updated_at,
});

const syncProjectListItem = (project: ProjectDetail) => {
  const nextItem = toProjectListItem(project);
  const existingIndex = projects.value.findIndex(
    (item) => item.id === project.id,
  );

  if (existingIndex === -1) {
    projects.value = [nextItem, ...projects.value];
    return;
  }

  const nextProjects = [...projects.value];
  nextProjects.splice(existingIndex, 1, {
    ...nextProjects[existingIndex],
    ...nextItem,
  });
  projects.value = nextProjects;
};

const syncModeWithProjectWorkflow = (project: ProjectDetail) => {
  if (currentRouteMode.value === "remake") {
    return;
  }
  activeMode.value = workflowTypeToMode(project.workflow_type);
};

const syncRouteProjectQuery = async (projectId?: number | null) => {
  const currentProjectId = Number(route.query.projectId ?? 0);
  const query = { ...route.query };

  if (projectId && currentProjectId === projectId) {
    return;
  }

  if (!projectId && !route.query.projectId) {
    return;
  }

  if (projectId) {
    query.projectId = String(projectId);
  } else {
    delete query.projectId;
  }

  await router.replace({
    path: route.path,
    query,
  });
};

const loadProjects = async (silent = false) => {
  if (!silent) {
    loadingHistory.value = true;
  }
  try {
    projects.value = await api<ProjectListItem[]>("/projects");
  } catch (error) {
    console.error(error);
  } finally {
    if (!silent) {
      loadingHistory.value = false;
    }
  }
};

const loadProjectDetail = async (projectId: number, silent = false) => {
  if (!silent) {
    loadingDetail.value = true;
  }
  try {
    const project = await api<ProjectDetail>(`/projects/${projectId}`);
    selectedProject.value = project;
    syncModeWithProjectWorkflow(project);
    syncProjectListItem(project);
    assistantFeedback.value = null;
    // Clear composer when viewing history
    selectedFile.value = null;
    selectedAudioFile.value = null;
    if (fileInputRef.value) {
      fileInputRef.value.value = "";
    }
    if (audioInputRef.value) {
      audioInputRef.value.value = "";
    }
    selectedUrls.value = [];
    inputText.value = "";
  } catch (error) {
    console.error(error);
  } finally {
    if (!silent) {
      loadingDetail.value = false;
    }
  }
};

watch(
  () => route.query.projectId,
  (value) => {
    const projectId = Number(value ?? 0);
    if (!Number.isInteger(projectId) || projectId <= 0) {
      if (selectedProject.value) {
        selectedProject.value = null;
      }
      return;
    }
    if (selectedProject.value?.id === projectId) {
      return;
    }
    void loadProjectDetail(projectId);
  },
);

watch(
  () => [selectedProject.value?.id, selectedProject.value?.status] as const,
  ([projectId, status]) => {
    clearProjectPollingTimer();
    if (!projectId || status !== "processing") {
      return;
    }

    projectPollingTimer = setInterval(() => {
      void loadProjectDetail(projectId, true);
    }, 1500);
  },
  { immediate: true },
);

const startRenameProject = (project: ProjectListItem) => {
  renamingProjectId.value = project.id;
  renameDraft.value = project.title || "新对话";
  renameModalError.value = "";
};

const cancelRenameProject = () => {
  renamingProjectId.value = null;
  renameDraft.value = "";
  renameModalError.value = "";
};

const applyProjectTitleLocally = (projectId: number, title: string) => {
  projects.value = projects.value.map((project) =>
    project.id === projectId ? { ...project, title } : project,
  );

  if (selectedProject.value?.id === projectId) {
    selectedProject.value = {
      ...selectedProject.value,
      title,
    };
  }
};

const submitRenameProject = async (projectId: number) => {
  if (renamingProjectPending.value) {
    return;
  }

  const title = renameDraft.value.trim();
  if (!title) {
    renameModalError.value = "标题不能为空";
    return;
  }

  renamingProjectPending.value = true;
  try {
    const updatedProject = await api<ProjectDetail>(`/projects/${projectId}`, {
      method: "PATCH",
      body: {
        title,
      },
    });
    applyProjectTitleLocally(projectId, updatedProject.title);
    cancelRenameProject();
  } catch (error) {
    renameModalError.value = extractErrorMessage(error, "重命名失败");
  } finally {
    renamingProjectPending.value = false;
  }
};

const submitCurrentRenameProject = () => {
  if (renamingProjectId.value === null) {
    return;
  }

  void submitRenameProject(renamingProjectId.value);
};

const projectToDelete = ref<ProjectListItem | null>(null);

const deleteProject = (project: ProjectListItem) => {
  projectToDelete.value = project;
};

const cancelDeleteProject = () => {
  projectToDelete.value = null;
};

const confirmDeleteProject = async () => {
  if (
    !projectToDelete.value ||
    deletingProjectId.value === projectToDelete.value.id
  ) {
    return;
  }

  const project = projectToDelete.value;
  deletingProjectId.value = project.id;
  try {
    await api(`/projects/${project.id}`, {
      method: "DELETE",
    });

    projects.value = projects.value.filter((item) => item.id !== project.id);

    if (selectedProject.value?.id === project.id) {
      const fallbackProject =
        projectsForCurrentMode.value[0] || projects.value[0];
      if (fallbackProject) {
        await syncRouteProjectQuery(fallbackProject.id);
        await loadProjectDetail(fallbackProject.id);
      } else {
        await syncRouteProjectQuery(null);
        resetComposer();
      }
    }

    if (renamingProjectId.value === project.id) {
      cancelRenameProject();
    }
  } catch (error) {
    errorMessage.value = extractErrorMessage(error, "删除失败");
  } finally {
    deletingProjectId.value = null;
    projectToDelete.value = null;
  }
};

const setActiveMode = (mode: ModeTab) => {
  activeMode.value = mode;
  isUserClearedMode.value = false;
  inputText.value = getModePrefill(mode);
  selectedFile.value = null;
  selectedAudioFile.value = null;
  selectedUrls.value = [];
  assistantFeedback.value = null;
  errorMessage.value = "";
  void focusTextarea();
};

const handleSidebarModeClick = (mode: ModeTab) => {
  activeMode.value = mode;
  resetComposer();
  void focusTextarea();
};

const handleNewChatClick = () => {
  activeMode.value = "script";
  resetComposer();
  void focusTextarea();
};

const handleUploadClick = () => {
  hideFilePopover();
  fileInputRef.value?.click();
};

const handleAudioUploadClick = () => {
  audioInputRef.value?.click();
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  target.value = "";
  errorMessage.value = "";
  if (!file) {
    return;
  }

  if (isRemakeSubmission.value) {
    if (!isImageFile(file) && !isVideoFile(file)) {
      errorMessage.value = "复刻模式只支持上传产品图或产品视频。";
      return;
    }
  } else if (!isVideoFile(file)) {
    errorMessage.value = "当前只支持上传视频文件。";
    return;
  }

  selectedFile.value = file;
  void focusTextarea();
};

const handleAudioFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  target.value = "";
  errorMessage.value = "";
  if (!file) {
    return;
  }

  if (!isAudioFile(file)) {
    errorMessage.value = "当前只支持上传音频文件。";
    return;
  }

  selectedAudioFile.value = file;
  void focusTextarea();
};

const buildSubmissionSourceLabel = () => {
  if (selectedFile.value) {
    return selectedFile.value.name;
  }

  if (selectedUrls.value.length > 0) {
    return selectedUrls.value[0];
  }

  if (isRemakeSubmission.value && remakeGeneration.value?.asset_name) {
    return `${remakeGeneration.value.asset_name}（已保存素材）`;
  }

  if (selectedProject.value) {
    return formatProjectSource(selectedProject.value);
  }

  return "未提供视频来源";
};

const setAssistantFeedback = (payload: AssistantFeedback) => {
  assistantFeedback.value = payload;
};

const retryAiAnalysis = async () => {
  if (!selectedProject.value || retryingAiAnalysis.value) {
    return;
  }

  retryingAiAnalysis.value = true;
  try {
    const updatedProject = await api<ProjectDetail>(
      `/projects/${selectedProject.value.id}/retry-ai-analysis`,
      {
        method: "POST",
      },
    );
    selectedProject.value = updatedProject;
    await loadProjects();
  } catch (error) {
    const message = extractErrorMessage(error, "AI 分析重试失败");
    selectedProject.value = {
      ...selectedProject.value,
      ecommerce_analysis: {
        ...(selectedProject.value.ecommerce_analysis || {
          title: getDefaultAnalysisTitle(selectedProject.value.workflow_type),
        }),
        content: `AI 分析失败：${message}`,
      },
    };
  } finally {
    retryingAiAnalysis.value = false;
  }
};

const submitRemakeGenerationRequest = async (
  projectId: number,
  options?: {
    objective?: string;
    asset?: File | null;
    audio?: File | null;
  },
) => {
  const formData = new FormData();
  if (options?.objective?.trim()) {
    formData.append("objective", options.objective.trim());
  }
  if (options?.asset) {
    formData.append("asset", options.asset);
  }
  if (options?.audio) {
    formData.append("audio", options.audio);
  }
  return api<ProjectDetail>(`/projects/${projectId}/remake-video`, {
    method: "POST",
    body: formData,
  });
};

const handleSend = async () => {
  errorMessage.value = "";
  const objective = inputText.value.trim();
  const displayObjective =
    objective ||
    (isRemakeSubmission.value
      ? "请基于这个对标视频生成一条适配我产品的视频"
      : "帮我分析这个视频");
  const sourceLabel = buildSubmissionSourceLabel();

  if (!isRemakeSubmission.value && !hasObjective.value) {
    setAssistantFeedback({
      status: "error",
      objective: displayObjective,
      sourceLabel,
      message:
        "这次我还没拿到有效指令。请再补充清楚一点你的目标，然后我继续处理。",
    });
    return;
  }

  if (
    !isRemakeSubmission.value &&
    !hasNewSourceSelection.value &&
    !selectedProject.value
  ) {
    setAssistantFeedback({
      status: "error",
      objective: displayObjective,
      sourceLabel,
      message:
        "这次我还没有可访问的视频来源。请先上传视频，或者粘贴一个 TikTok / 抖音 / Shorts 链接。",
    });
    return;
  }

  if (isRemakeSubmission.value) {
    if (selectedProject.value?.status !== "ready") {
      setAssistantFeedback({
        status: "error",
        objective: displayObjective,
        sourceLabel,
        message:
          processingStatusMessage.value ||
          "当前项目还在处理中，请先等待分析或上一轮复刻结束。",
      });
      return;
    }
  }

  setAssistantFeedback({
    status: "pending",
    objective: displayObjective,
    sourceLabel,
    message: isRemakeSubmission.value
      ? "正在创建视频复刻任务，请稍等。"
      : "正在创建后台任务，请稍等。",
  });
  sending.value = true;

  try {
    let project: ProjectDetail;
    const shouldAutoTriggerRemakeGeneration =
      !isRemakeSubmission.value && activeMode.value === "remake";

    if (isRemakeSubmission.value) {
      project = await submitRemakeGenerationRequest(selectedProject.value!.id, {
        objective,
        asset: selectedFile.value,
        audio: selectedAudioFile.value,
      });
    } else if (selectedFile.value) {
      const formData = new FormData();
      formData.append("file", selectedFile.value);
      formData.append(
        "title",
        buildProjectTitle(activeMode.value, selectedFile.value.name),
      );
      formData.append("objective", inputText.value.trim());
      formData.append("workflow_type", modeToWorkflowType(activeMode.value));
      project = await api<ProjectDetail>("/projects/upload", {
        method: "POST",
        body: formData,
      });
    } else if (selectedUrls.value.length > 0) {
      // New source input always starts a new workflow instead of mutating the current project.
      const url = selectedUrls.value[0];
      project = await api<ProjectDetail>("/projects", {
        method: "POST",
        body: {
          source_url: url,
          title: buildProjectTitle(activeMode.value, url),
          objective,
          workflow_type: modeToWorkflowType(activeMode.value),
        },
      });
    } else {
      project = await api<ProjectDetail>(
        `/projects/${selectedProject.value!.id}/refresh`,
        {
          method: "POST",
          body: {
            objective,
            workflow_type: modeToWorkflowType(activeMode.value),
          },
        },
      );
    }

    if (shouldAutoTriggerRemakeGeneration && project.workflow_type === "remake") {
      selectedProject.value = project;
      syncModeWithProjectWorkflow(project);
      syncProjectListItem(project);
      pipelineExpanded.value = true;
      await syncRouteProjectQuery(project.id);
      await loadProjects();

      setAssistantFeedback({
        status: "pending",
        objective: displayObjective,
        sourceLabel,
        message: "对标视频解析完成，正在调用万相生成复刻视频。",
      });

      try {
        project = await submitRemakeGenerationRequest(project.id, {
          objective: objective || project.objective,
          audio: selectedAudioFile.value,
        });
      } catch (remakeError) {
        errorMessage.value = extractErrorMessage(
          remakeError,
          "万相复刻视频生成失败",
        );
      }
    }

    selectedProject.value = project;
    syncModeWithProjectWorkflow(project);
    syncProjectListItem(project);
    pipelineExpanded.value = true;
    assistantFeedback.value = null;
    await syncRouteProjectQuery(project.id);
    await loadProjects();
    inputText.value = isRemakeSubmission.value
      ? getModePrefill(activeMode.value)
      : "";
    if (inputText.value === "") {
      isUserClearedMode.value = true;
    }
    selectedFile.value = null;
    selectedAudioFile.value = null;
    if (fileInputRef.value) {
      fileInputRef.value.value = "";
    }
    if (audioInputRef.value) {
      audioInputRef.value.value = "";
    }
    selectedUrls.value = [];
  } catch (error) {
    setAssistantFeedback({
      status: "error",
      objective: displayObjective,
      sourceLabel,
      message: extractErrorMessage(error, "发送失败"),
    });
  } finally {
    sending.value = false;
  }
};

const showLogoutModal = ref(false);

const handleLogoutClick = () => {
  showLogoutModal.value = true;
};

const confirmLogout = async () => {
  showLogoutModal.value = false;
  await auth.logout();
  navigateTo("/auth/login");
};

const cancelLogout = () => {
  showLogoutModal.value = false;
};

const handleOpenSystemSettings = async () => {
  await navigateTo({
    path: "/settings/system",
    query: selectedProject.value
      ? {
          projectId: String(selectedProject.value.id),
        }
      : undefined,
  });
};

await loadProjects();
const requestedProjectId = Number(route.query.projectId ?? 0);
if (Number.isInteger(requestedProjectId) && requestedProjectId > 0) {
  const initialProject =
    projectsForCurrentMode.value.find(
      (project) => project.id === requestedProjectId,
    ) || projects.value.find((project) => project.id === requestedProjectId);
  if (initialProject) {
    // Clear composer before loading
    selectedFile.value = null;
    selectedAudioFile.value = null;
    if (fileInputRef.value) {
      fileInputRef.value.value = "";
    }
    if (audioInputRef.value) {
      audioInputRef.value.value = "";
    }
    selectedUrls.value = [];
    inputText.value = "";
    await loadProjectDetail(initialProject.id);
    await syncRouteProjectQuery(initialProject.id);
  } else {
    resetComposer();
  }
}

watch(() => route.query.projectId, (newVal) => {
  const pid = Number(newVal ?? 0);
  if (pid > 0) {
    loadProjectDetail(pid).catch(console.error);
  } else {
    resetComposer();
  }
});

const getRemakeGenerationStatusLabel = (status: string) => {
  if (status === "ready") return "已完成";
  if (status === "processing") return "生成中";
  if (status === "failed") return "失败";
  return "待开始";
};

const getRemakeGenerationStatusClass = (status: string) => {
  if (status === "ready") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200";
  }
  if (status === "processing") {
    return "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-200";
  }
  if (status === "failed") {
    return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200";
  }
  return "border-slate-200 bg-slate-50 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300";
};

const formatVideoProviderLabel = (provider: string | null | undefined) => {
  const normalized = (provider || "").trim().toLowerCase();
  const labels: Record<string, string> = {
    custom: "自定义 OpenAI 兼容视频服务",
    doubao: "豆包视频 / 火山方舟",
    kling: "可灵视频 / Kling",
    openai: "OpenAI 兼容视频接口",
    qwen: "通义万相 / DashScope",
    veo: "Google Veo",
  };
  return labels[normalized] || provider || "";
};

const remakeGenerationProviderLabel = computed(() =>
  formatVideoProviderLabel(remakeGeneration.value?.provider),
);

const handleClearMode = () => {
  isUserClearedMode.value = true;
  inputText.value = "";
  void focusTextarea();
};
</script>

<template>
  <div
    class="flex h-full w-full bg-[#f9f9f9] dark:bg-[#121212] font-sans antialiased text-[#1a1a1a] dark:text-[#f3f4f6]"
  >
    <!-- Right Dashboard -->
    <main
      class="flex-1 flex flex-col h-full relative bg-[#ffffff] dark:bg-[#121212]"
    >
      <!-- Main Chat/Result Area -->
      <div
        ref="chatScrollContainer"
        class="flex-1 overflow-y-auto px-6 lg:px-[120px] pb-[200px] pt-4 custom-scrollbar scroll-smooth"
      >
        <!-- Welcome State -->
        <div
          v-if="!hasConversation"
          class="h-full flex flex-col items-center justify-center pb-[10vh]"
        >
          <h1
            class="text-[28px] font-bold text-[#1a1a1a] dark:text-white mb-3 tracking-tight"
          >
            {{
              activeMode === "script"
                ? "TikTok 电商效果分析"
                : activeMode === "remake"
                  ? "一键复刻对标爆款"
                  : "智能创作爆款脚本文案"
            }}
          </h1>
          <p
            class="text-[15px] text-[#666] dark:text-[#999] mb-10 max-w-lg text-center leading-relaxed"
          >
            上传本地视频，或者直接粘贴短视频链接，AI将为您提供最出色的方案解析。目前支持所有主流短视频平台。
          </p>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-4xl">
            <button
              @click="setActiveMode('script')"
              class="p-4 rounded-2xl bg-[#f8f9fa] dark:bg-white/5 hover:bg-[#f0f2f5] dark:hover:bg-white/10 border border-transparent transition-all flex flex-col items-start gap-3"
            >
              <div
                class="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center"
              >
                <LucideIcon name="Captions" class="w-4 h-4" />
              </div>
              <div class="text-left">
                <div
                  class="font-semibold text-[#1a1a1a] dark:text-white text-[15px] mb-1"
                >
                  视频分析
                </div>
                <div class="text-[13px] text-[#666] dark:text-[#999]">
                  输出 Hook、卖点、CTA、评分和改进建议...
                </div>
              </div>
              <LucideIcon
                name="ArrowRight"
                class="w-4 h-4 text-[#bfbfbf] mt-auto ml-auto"
              />
            </button>
            <button
              @click="setActiveMode('remake')"
              class="p-4 rounded-2xl bg-[#f8f9fa] dark:bg-white/5 hover:bg-[#f0f2f5] dark:hover:bg-white/10 border border-transparent transition-all flex flex-col items-start gap-3"
            >
              <div
                class="w-8 h-8 rounded-full bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center justify-center"
              >
                <LucideIcon name="Video" class="w-4 h-4" />
              </div>
              <div class="text-left">
                <div
                  class="font-semibold text-[#1a1a1a] dark:text-white text-[15px] mb-1"
                >
                  复刻爆款
                </div>
                <div class="text-[13px] text-[#666] dark:text-[#999]">
                  上传产品图或产品视频，按对标视频生成复刻短片...
                </div>
              </div>
              <LucideIcon
                name="ArrowRight"
                class="w-4 h-4 text-[#bfbfbf] mt-auto ml-auto"
              />
            </button>
            <button
              @click="setActiveMode('create')"
              class="p-4 rounded-2xl bg-[#f8f9fa] dark:bg-white/5 hover:bg-[#f0f2f5] dark:hover:bg-white/10 border border-transparent transition-all flex flex-col items-start gap-3"
            >
              <div
                class="w-8 h-8 rounded-full bg-violet-100 dark:bg-violet-500/20 text-violet-600 dark:text-violet-400 flex items-center justify-center"
              >
                <LucideIcon name="Sparkles" class="w-4 h-4" />
              </div>
              <div class="text-left">
                <div
                  class="font-semibold text-[#1a1a1a] dark:text-white text-[15px] mb-1"
                >
                  创作爆款
                </div>
                <div class="text-[13px] text-[#666] dark:text-[#999]">
                  根据视频类型、客群、卖点和风格生成新脚本...
                </div>
              </div>
              <LucideIcon
                name="ArrowRight"
                class="w-4 h-4 text-[#bfbfbf] mt-auto ml-auto"
              />
            </button>
          </div>
        </div>

        <!-- Result State: Styled like Doubao Chat -->
        <div
          v-else
          class="max-w-[800px] mx-auto w-full flex flex-col gap-8 pb-10"
        >
          <!-- User Message Bubble (Objective) -->
          <div class="flex items-start gap-4 flex-row-reverse w-full">
            <div
              class="w-[36px] h-[36px] rounded-full shrink-0 overflow-hidden border border-[#e5e5e5] dark:border-white/10"
            >
              <img
                src="~/assets/image/icon.webp"
                class="w-full h-full object-cover"
              />
            </div>
            <div
              class="max-w-[80%] bg-[#f4f4f5] dark:bg-[#1f1f1f] rounded-[20px] rounded-tr-[4px] px-5 py-4 text-[15.5px] text-[#1a1a1a] dark:text-white leading-[1.7] flex flex-col gap-3"
            >
              <!-- 文本内容 -->
              <div class="whitespace-pre-wrap">
                {{ activeConversationObjective || "帮我分析这个视频" }}
              </div>

              <!-- 附件卡片区 -->
              <div
                v-if="selectedProject || assistantFeedback"
                class="flex flex-col gap-3.5 mt-1 text-[15px]"
              >
                <!-- 链接显示 -->
                <a
                  v-if="
                    (selectedProject?.source_type === 'url' &&
                      selectedProject?.source_url) ||
                    (assistantFeedback?.sourceLabel?.startsWith('http') &&
                      assistantFeedback?.sourceLabel)
                  "
                  :href="
                    selectedProject?.source_url ||
                    assistantFeedback?.sourceLabel
                  "
                  target="_blank"
                  class="text-[#1a1a1a] dark:text-white font-medium underline underline-offset-4 decoration-[1.5px] break-all hover:text-blue-600 transition-colors inline-block"
                >
                  {{
                    selectedProject?.source_url ||
                    assistantFeedback?.sourceLabel
                  }}
                </a>

                <!-- 视频卡片悬浮 -->
                <div
                  class="mt-1 flex flex-col gap-2 w-fit"
                  v-if="
                    selectedProject?.source_name !== '未知文件' ||
                    assistantFeedback?.sourceLabel
                  "
                >
                  <div
                    @click="
                      activeDetailTab = 'analysis';
                      showVideoDetailModal = true;
                    "
                    class="w-[100px] h-[100px] rounded-xl bg-[#2a303c] flex items-center justify-center relative shadow-[0_4px_12px_rgba(0,0,0,0.1)] cursor-pointer hover:opacity-90 transition-all hover:-translate-y-0.5 overflow-hidden group"
                  >
                    <!-- Video Background if available -->
                    <video
                      v-if="
                        selectedProjectPreviewUrl ||
                        (assistantFeedback?.sourceLabel &&
                          !assistantFeedback.sourceLabel.startsWith('http'))
                      "
                      :src="
                        selectedProjectPreviewUrl ||
                        assistantFeedback?.sourceLabel
                      "
                      preload="metadata"
                      muted
                      class="absolute inset-0 w-full h-full object-cover opacity-50 group-hover:opacity-70 transition-opacity"
                    ></video>

                    <!-- 内发光倒角 -->
                    <div
                      class="absolute inset-0 bg-white/5 rounded-xl border border-white/5 pointer-events-none z-10"
                    ></div>

                    <div
                      class="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center z-10"
                    >
                      <LucideIcon
                        name="Video"
                        class="w-5 h-5 text-white ml-0.5 opacity-90 drop-shadow-md"
                        style="fill: white"
                      />
                    </div>

                    <div
                      class="absolute top-2 right-2 w-5 h-5 bg-black/50 backdrop-blur-sm rounded-md flex items-center justify-center z-10"
                    >
                      <LucideIcon
                        name="Video"
                        class="w-3 h-3 text-white opacity-90"
                      />
                    </div>
                  </div>
                  <div
                    class="text-[13px] font-medium text-[#737373] dark:text-[#999] max-w-[100px] truncate px-0.5"
                    :title="
                      selectedProject?.source_name ||
                      assistantFeedback?.sourceLabel
                    "
                  >
                    {{
                      selectedProject?.title ||
                      selectedProject?.source_name ||
                      assistantFeedback?.sourceLabel ||
                      "视频文件"
                    }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="assistantFeedback" class="flex items-start gap-4 w-full">
            <div
              class="w-[36px] h-[36px] rounded-full shrink-0 overflow-hidden border border-[#e5e5e5] dark:border-white/10 shadow-sm"
            >
              <img
                src="~/assets/image/icon.webp"
                class="w-full h-full object-cover p-1 bg-white"
              />
            </div>
            <div class="flex-1 max-w-[100%]">
              <div
                class="rounded-2xl border px-5 py-4 text-[15px] leading-[1.8]"
                :class="
                  assistantFeedback.status === 'error'
                    ? 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-100'
                    : 'border-slate-200 bg-white text-[#1a1a1a] dark:border-white/10 dark:bg-[#1f1f1f] dark:text-[#f3f4f6]'
                "
              >
                <div class="flex items-start gap-3">
                  <div
                    class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                    :class="
                      assistantFeedback.status === 'error'
                        ? 'bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-200'
                        : 'bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-white'
                    "
                  >
                    <LucideIcon
                      v-if="assistantFeedback.status === 'error'"
                      name="AlertTriangle"
                      class="h-4 w-4"
                      :stroke-width="2"
                    />
                    <LucideIcon
                      v-else
                      name="LoaderCircle"
                      class="h-4 w-4 animate-spin"
                      :stroke-width="2"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="text-[13px] font-medium opacity-70">
                      {{
                        assistantFeedback.status === "error"
                          ? "AI 返回错误"
                          : "AI 正在处理"
                      }}
                    </div>
                    <div class="mt-1 whitespace-pre-wrap">
                      {{ assistantFeedback.message }}
                    </div>
                    <div class="mt-3 text-[12px] opacity-70 break-all">
                      来源：{{ assistantFeedback.sourceLabel }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- AI Response Bubble -->
          <div
            v-else-if="selectedProject"
            class="flex items-start gap-4 w-full"
          >
            <div
              class="w-[36px] h-[36px] rounded-full shrink-0 overflow-hidden border border-[#e5e5e5] dark:border-white/10 shadow-sm"
            >
              <!-- System or AI avatar -->
              <img
                src="~/assets/image/icon.webp"
                class="w-full h-full object-cover p-1 bg-white"
              />
            </div>
            <div class="flex-1 max-w-[100%]">
              <div
                class="text-[#1a1a1a] dark:text-[#f3f4f6] text-[15.5px] leading-[1.8] rounded-2xl p-1"
              >
                <TaskTimeline
                  :tasks="pipelineTasks"
                  :summary="pipelineSummary"
                  :is-failed="selectedProject.status === 'failed'"
                  :failed-reason="selectedProject.summary"
                />

                <div class="mb-4 text-[#666] text-[14px]">
                  帮您分析了来源：
                  <a
                    v-if="selectedProject.source_type === 'url'"
                    :href="selectedProject.source_url"
                    target="_blank"
                    class="text-blue-600 hover:underline break-all"
                    >{{ selectedProject.source_url }}</a
                  ><span v-else>{{ selectedProject.source_name }}</span>
                </div>

                <!-- AI Analysis -->
                <div class="mb-8">
                  <div
                    class="mb-3 flex items-center justify-between gap-3 border-b border-[#eee] pb-2 dark:border-white/10"
                  >
                    <h3
                      class="font-bold text-[18px] text-[#1a1a1a] dark:text-white flex items-center gap-2"
                    >
                      <LucideIcon
                        name="Sparkles"
                        class="w-5 h-5 text-purple-500"
                      />
                      {{ analysisPanelTitle }}
                    </h3>
                    <button
                      @click="retryAiAnalysis"
                      :disabled="
                        retryingAiAnalysis || selectedProject.status !== 'ready'
                      "
                      class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors"
                      :class="
                        retryingAiAnalysis || selectedProject.status !== 'ready'
                          ? 'border-slate-200 text-slate-400 cursor-not-allowed dark:border-white/10 dark:text-slate-500'
                          : 'border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5'
                      "
                    >
                      <LucideIcon
                        :name="
                          retryingAiAnalysis ? 'LoaderCircle' : 'RefreshCcw'
                        "
                        class="w-3.5 h-3.5"
                        :class="retryingAiAnalysis ? 'animate-spin' : ''"
                        :stroke-width="2"
                      />
                      {{
                        retryingAiAnalysis
                          ? "重试中..."
                          : selectedProject.status !== "ready"
                            ? currentPendingTaskStep?.title
                              ? `处理中：${currentPendingTaskStep.title}`
                              : "等待任务完成"
                            : analysisRetryLabel
                      }}
                    </button>
                  </div>
                  <template
                    v-if="
                      selectedProject.workflow_type === 'remake' &&
                      hasStructuredRemakeAnalysis
                    "
                  >
                    <p
                      v-if="remakeAnalysisSummary"
                      class="text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                    >
                      {{ remakeAnalysisSummary }}
                    </p>

                    <div
                      v-if="remakeAdviceCards.length > 0"
                      class="mt-4 grid gap-3 md:grid-cols-2"
                    >
                      <div
                        v-for="card in remakeAdviceCards"
                        :key="card.title"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5"
                      >
                        <div
                          class="text-[12px] uppercase tracking-[0.18em] text-slate-400"
                        >
                          {{ card.title }}
                        </div>
                        <div
                          class="mt-1 text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                        >
                          {{ card.body }}
                        </div>
                      </div>
                    </div>

                    <div v-if="remakeScriptCards.length > 0" class="mt-4">
                      <div
                        class="mb-2 text-[13px] font-medium text-slate-700 dark:text-slate-200"
                      >
                        AI 复刻视频文案脚本
                      </div>
                      <div class="grid gap-3">
                        <div
                          v-for="item in remakeScriptCards"
                          :key="`${item.title}-${item.timing}`"
                          class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5"
                        >
                          <div
                            class="flex flex-wrap items-center gap-2 text-[13px] font-medium text-[#1a1a1a] dark:text-white"
                          >
                            <span>{{ item.title }}</span>
                            <span
                              v-if="item.timing"
                              class="rounded-full border border-slate-200 px-2 py-0.5 text-[12px] font-mono text-slate-500 dark:border-white/10 dark:text-slate-300"
                            >
                              {{ item.timing }}
                            </span>
                          </div>
                          <div class="mt-2 space-y-1.5 text-[14px] leading-relaxed">
                            <div class="text-[#1a1a1a] dark:text-white">
                              口播：{{ item.voiceover }}
                            </div>
                            <div class="text-slate-600 dark:text-slate-300">
                              字幕：{{ item.subtitle }}
                            </div>
                            <div class="text-slate-500 dark:text-slate-400">
                              镜头：{{ item.direction }}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <div
                        class="text-[12px] uppercase tracking-[0.18em] text-slate-400"
                      >
                        万相生成方案
                      </div>
                      <div
                        class="mt-2 text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                      >
                        {{ remakeWanxiangPrompt }}
                      </div>
                      <ul
                        v-if="remakeWanxiangNotes.length > 0"
                        class="mt-3 space-y-2 pl-5 text-[13px] text-slate-600 dark:text-slate-300"
                      >
                        <li v-for="note in remakeWanxiangNotes" :key="note">
                          {{ note }}
                        </li>
                      </ul>
                    </div>
                  </template>

                  <div
                    v-else
                    class="prose prose-sm max-w-none whitespace-pre-wrap"
                    :class="
                      ecommerceAnalysisLooksFailed
                        ? 'text-rose-600 dark:text-rose-300'
                        : ''
                    "
                  >
                    {{
                      selectedProject.ecommerce_analysis?.content ||
                      (selectedProject.status === "ready"
                        ? analysisEmptyReadyMessage
                        : analysisProcessingMessage)
                    }}
                  </div>
                </div>

                <div v-if="hasVisibleSourceAnalysis" class="mb-8">
                  <h3
                    class="font-bold text-[18px] mb-3 text-[#1a1a1a] dark:text-white border-b border-[#eee] dark:border-white/10 pb-2 flex items-center gap-2"
                  >
                    <LucideIcon name="ImagePlus" class="w-5 h-5 text-amber-500" />
                    关键帧与视觉特征
                  </h3>

                  <div
                    class="rounded-2xl border border-[#eee] bg-white p-4 dark:border-white/10 dark:bg-[#171717]"
                  >
                    <p
                      v-if="sourceVisualFeatures?.summary"
                      class="text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                    >
                      {{ sourceVisualFeatures.summary }}
                    </p>

                    <div
                      v-if="sourceVisualMetaBadges.length > 0"
                      class="mt-4 flex flex-wrap gap-2"
                    >
                      <span
                        v-for="badge in sourceVisualMetaBadges"
                        :key="badge.label"
                        class="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[12px] text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300"
                      >
                        {{ badge.label }} · {{ badge.value }}
                      </span>
                    </div>

                    <div
                      v-if="sourceVisualSignalCards.length > 0"
                      class="mt-4 grid gap-3 md:grid-cols-2"
                    >
                      <div
                        v-for="card in sourceVisualSignalCards"
                        :key="card.label"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-white/10 dark:bg-white/5"
                      >
                        <div
                          class="text-[12px] uppercase tracking-[0.18em] text-slate-400"
                        >
                          {{ card.label }}
                        </div>
                        <div
                          class="mt-1 text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                        >
                          {{ card.value }}
                        </div>
                      </div>
                    </div>

                    <div
                      v-if="sourceVisualFeatures?.dominant_palette?.length"
                      class="mt-4"
                    >
                      <div
                        class="mb-2 text-[13px] font-medium text-slate-700 dark:text-slate-200"
                      >
                        主色板
                      </div>
                      <div class="flex flex-wrap gap-3">
                        <div
                          v-for="color in sourceVisualFeatures.dominant_palette"
                          :key="color"
                          class="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 dark:border-white/10 dark:bg-white/5"
                        >
                          <span
                            class="h-4 w-4 rounded-full border border-black/10"
                            :style="{ backgroundColor: color }"
                          />
                          <span
                            class="font-mono text-[12px] text-slate-600 dark:text-slate-300"
                          >
                            {{ color }}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div v-if="sourceReferenceFrames.length > 0" class="mt-4">
                      <div
                        class="mb-2 text-[13px] font-medium text-slate-700 dark:text-slate-200"
                      >
                        对标视频关键帧
                      </div>
                      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                        <div
                          v-for="(frame, index) in sourceReferenceFrames"
                          :key="`${index}-${frame.slice(0, 32)}`"
                          class="overflow-hidden rounded-xl border border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/5"
                        >
                          <img
                            :src="frame"
                            :alt="`对标关键帧 ${index + 1}`"
                            class="aspect-[9/16] w-full object-cover"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Full Script Markdown-like rendering -->
                <div
                  v-if="selectedProject.script_overview?.full_text"
                  class="mb-8"
                >
                  <h3
                    class="font-bold text-[18px] mb-3 text-[#1a1a1a] dark:text-white border-b border-[#eee] dark:border-white/10 pb-2 flex items-center gap-2"
                  >
                    <LucideIcon name="Text" class="w-5 h-5 text-blue-500" />
                    字幕整理
                  </h3>
                  <p class="whitespace-pre-wrap">
                    {{ selectedProject.script_overview.full_text }}
                  </p>
                </div>

                <!-- Transcription -->
                <div
                  v-if="selectedProject.timeline_segments?.length > 0"
                  class="mb-8"
                >
                  <h3
                    class="font-bold text-[18px] mb-3 text-[#1a1a1a] dark:text-white border-b border-[#eee] dark:border-white/10 pb-2 flex items-center gap-2"
                  >
                    <LucideIcon
                      name="MessageSquareText"
                      class="w-5 h-5 text-green-500"
                    />
                    字幕时间轴
                  </h3>
                  <ul class="space-y-3 mt-4 list-disc pl-5">
                    <li
                      v-for="segment in selectedProject.timeline_segments"
                      :key="segment.id"
                      class="text-[#1a1a1a] dark:text-white marker:text-[#ccc]"
                    >
                      <span class="font-bold mr-2"
                        >{{ segment.speaker || t("videoLab.caption") }}:</span
                      >
                      <span>{{ segment.content }}</span>
                      <span
                        class="text-[#999] text-[13px] ml-2 font-mono bg-slate-50 dark:bg-white/5 px-1.5 py-0.5 rounded"
                        >{{
                          formatRange(segment.start_ms, segment.end_ms)
                        }}</span
                      >
                    </li>
                  </ul>
                </div>

                <div v-if="hasVisibleRemakeGeneration" class="mb-8">
                  <h3
                    class="font-bold text-[18px] mb-3 text-[#1a1a1a] dark:text-white border-b border-[#eee] dark:border-white/10 pb-2 flex items-center gap-2"
                  >
                    <LucideIcon
                      name="Clapperboard"
                      class="w-5 h-5 text-amber-500"
                    />
                    视频复刻生成
                  </h3>

                  <div
                    class="rounded-2xl border border-[#eee] bg-white p-4 dark:border-white/10 dark:bg-[#171717]"
                  >
                    <div class="flex flex-wrap items-center gap-2">
                      <span
                        class="rounded-full border px-2.5 py-1 text-[12px] font-medium"
                        :class="
                          getRemakeGenerationStatusClass(
                            remakeGeneration?.status || 'idle',
                          )
                        "
                      >
                        {{
                          getRemakeGenerationStatusLabel(
                            remakeGeneration?.status || "idle",
                          )
                        }}
                      </span>
                      <span
                        v-if="remakeGenerationProviderLabel"
                        class="rounded-full border border-slate-200 px-2.5 py-1 text-[12px] text-slate-600 dark:border-white/10 dark:text-slate-300"
                      >
                        {{ remakeGenerationProviderLabel }}
                      </span>
                      <span
                        v-if="remakeGeneration?.model"
                        class="rounded-full border border-slate-200 px-2.5 py-1 text-[12px] text-slate-600 dark:border-white/10 dark:text-slate-300"
                      >
                        {{ remakeGeneration.model }}
                      </span>
                    </div>

                    <div class="mt-4 grid gap-3 md:grid-cols-2">
                      <div
                        v-if="remakeGeneration?.asset_name"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
                      >
                        <div
                          class="text-[12px] uppercase tracking-[0.18em] text-slate-400"
                        >
                          产品素材
                        </div>
                        <div class="mt-1 font-medium">
                          {{ remakeGeneration.asset_name }}
                        </div>
                        <div class="mt-1 text-slate-500 dark:text-slate-400">
                          {{
                            remakeGeneration.asset_type === "image"
                              ? "图片参考"
                              : remakeGeneration.asset_type === "video"
                                ? "视频参考（已自动抽帧）"
                                : "未上传产品素材，已按脚本直接生成"
                          }}
                        </div>
                      </div>

                      <div
                        v-if="remakeGeneration?.audio_name"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
                      >
                        <div
                          class="text-[12px] uppercase tracking-[0.18em] text-slate-400"
                        >
                          配音素材
                        </div>
                        <div class="mt-1 font-medium">
                          {{ remakeGeneration.audio_name }}
                        </div>
                        <div class="mt-1 text-slate-500 dark:text-slate-400">
                          将作为万相音频驱动输入
                        </div>
                      </div>

                      <div
                        v-if="remakeGeneration?.provider_task_id"
                        class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
                      >
                        <div
                          class="text-[12px] uppercase tracking-[0.18em] text-slate-400"
                        >
                          任务 ID
                        </div>
                        <div class="mt-1 break-all font-mono text-[12px]">
                          {{ remakeGeneration.provider_task_id }}
                        </div>
                      </div>
                    </div>

                    <div v-if="remakeReferenceFrames.length > 0" class="mt-4">
                      <div
                        class="mb-2 text-[13px] font-medium text-slate-700 dark:text-slate-200"
                      >
                        参考抽帧
                      </div>
                      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                        <div
                          v-for="(frame, index) in remakeReferenceFrames"
                          :key="`${index}-${frame.slice(0, 32)}`"
                          class="overflow-hidden rounded-xl border border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/5"
                        >
                          <img
                            :src="frame"
                            :alt="`参考帧 ${index + 1}`"
                            class="aspect-[9/16] w-full object-cover"
                          />
                        </div>
                      </div>
                    </div>

                    <div v-if="remakeGeneration?.audio_url" class="mt-4">
                      <div
                        class="mb-2 text-[13px] font-medium text-slate-700 dark:text-slate-200"
                      >
                        音频预览
                      </div>
                      <audio
                        :src="remakeGeneration.audio_url"
                        controls
                        class="w-full"
                      ></audio>
                    </div>

                    <div v-if="remakeGeneration?.result_video_url" class="mt-4">
                      <div
                        class="mb-2 text-[13px] font-medium text-slate-700 dark:text-slate-200"
                      >
                        生成结果
                      </div>
                      <video
                        :src="remakeGeneration.result_video_url"
                        controls
                        class="w-full rounded-xl border border-slate-200 bg-black dark:border-white/10"
                      ></video>
                    </div>

                    <div
                      v-if="remakeGeneration?.error_detail"
                      class="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200"
                    >
                      {{ remakeGeneration.error_detail }}
                    </div>
                  </div>

                  <div class="mt-4 grid gap-4">
                    <div
                      v-if="remakeGeneration?.script"
                      class="rounded-2xl border border-[#eee] bg-white p-4 dark:border-white/10 dark:bg-[#171717]"
                    >
                      <div
                        class="mb-2 flex items-center gap-2 text-[14px] font-semibold text-[#1a1a1a] dark:text-white"
                      >
                        <LucideIcon
                          name="FileText"
                          class="w-4 h-4 text-blue-500"
                        />
                        生成脚本
                      </div>
                      <div
                        class="whitespace-pre-wrap text-[14px] text-[#1a1a1a] dark:text-white"
                      >
                        {{ remakeGeneration.script }}
                      </div>
                    </div>

                    <div
                      v-if="remakeGeneration?.storyboard"
                      class="rounded-2xl border border-[#eee] bg-white p-4 dark:border-white/10 dark:bg-[#171717]"
                    >
                      <div
                        class="mb-2 flex items-center gap-2 text-[14px] font-semibold text-[#1a1a1a] dark:text-white"
                      >
                        <LucideIcon
                          name="Clapperboard"
                          class="w-4 h-4 text-amber-500"
                        />
                        生成分镜
                      </div>
                      <div
                        class="whitespace-pre-wrap text-[14px] text-[#1a1a1a] dark:text-white"
                      >
                        {{ remakeGeneration.storyboard }}
                      </div>
                    </div>

                    <div
                      v-if="remakeGeneration?.prompt"
                      class="rounded-2xl border border-[#eee] bg-white p-4 dark:border-white/10 dark:bg-[#171717]"
                    >
                      <div
                        class="mb-2 flex items-center gap-2 text-[14px] font-semibold text-[#1a1a1a] dark:text-white"
                      >
                        <LucideIcon
                          name="Sparkles"
                          class="w-4 h-4 text-violet-500"
                        />
                        {{
                          remakeGeneration?.provider === "qwen"
                            ? "万相生成提示词"
                            : "生成提示词"
                        }}
                      </div>
                      <div
                        class="whitespace-pre-wrap break-words text-[14px] text-[#1a1a1a] dark:text-white"
                      >
                        {{ remakeGeneration.prompt }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 更新时间 -->
                <div
                  class="flex items-center gap-1.5 mt-6 pt-2 text-[13px] text-[#9ca3af] dark:text-[#6b7280] cursor-pointer hover:text-[#6b7280] dark:hover:text-[#9ca3af] transition-colors select-none w-max"
                >
                  <LucideIcon name="Copy" class="w-[15px] h-[15px]" />
                  <span class="font-mono mt-[1px]">{{
                    new Date(
                      selectedProject.updated_at || selectedProject.created_at,
                    ).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom Input Area (Fixed) -->
      <div
        class="absolute bottom-0 left-0 right-0 p-4 lg:px-[120px] bg-gradient-to-t from-white via-white dark:from-[#121212] dark:via-[#121212] to-transparent pointer-events-none pb-8"
      >
        <div class="max-w-[800px] mx-auto pointer-events-auto">
          <div
            v-if="errorMessage && !assistantFeedback"
            class="mb-2 px-4 py-2 bg-red-50 text-red-600 rounded-xl text-sm border border-red-100 flex items-center gap-2 mx-auto w-fit shadow-sm"
          >
            <LucideIcon name="AlertCircle" class="w-4 h-4" />
            {{ errorMessage }}
          </div>

          <div
            class="relative rounded-3xl bg-white dark:bg-[#1f1f1f] border border-[#e5e5e5] dark:border-white/10 shadow-[0_4px_30px_rgba(0,0,0,0.06)] dark:shadow-[0_4px_30px_rgba(0,0,0,0.3)] transition-all overflow-visible focus-within:ring-2 focus-within:ring-blue-100 dark:focus-within:ring-blue-500/20 focus-within:border-blue-300 dark:focus-within:border-blue-500/50"
          >
            <!-- Source Tags -->
            <div
              v-if="selectedSourceCard && selectedSourceCard.length > 0"
              class="px-4 pt-4 pb-1 flex flex-wrap gap-2"
            >
              <div
                v-for="(card, index) in selectedSourceCard"
                :key="card.key || index"
                class="inline-flex items-center gap-2.5 rounded-2xl border border-[#ececec] bg-white px-3 py-2 shadow-[0_4px_12px_rgba(15,23,42,0.05)] max-w-[320px]"
              >
                <div
                  class="flex items-center justify-center w-9 h-9 rounded-full bg-[#efefef] text-[#3f3f46] shrink-0"
                >
                  <LucideIcon
                    :name="card.icon"
                    class="w-4 h-4"
                    :stroke-width="1.8"
                  />
                </div>

                <div class="flex-1 min-w-0 overflow-hidden">
                  <div
                    class="text-[15px] font-semibold text-[#1a1a1a] leading-tight"
                  >
                    {{ card.title }}
                  </div>
                  <div
                    class="text-[13px] text-[#9ca3af] truncate leading-tight mt-0.5"
                  >
                    {{ card.subtitle }}
                  </div>
                </div>

                <button
                  v-if="card.dismissible"
                  @click.stop.prevent="clearSelectedSource(card.clearKey)"
                  class="flex items-center justify-center w-8 h-8 rounded-full text-[#9ca3af] hover:bg-[#f3f4f6] hover:text-[#6b7280] transition-colors shrink-0 z-10 relative"
                >
                  <LucideIcon name="X" class="w-5 h-5" :stroke-width="2" />
                </button>
              </div>
            </div>

            <!-- Textarea -->
            <textarea
              ref="textareaRef"
              v-model="inputText"
              rows="1"
              class="w-full bg-transparent resize-none outline-none px-5 py-3.5 text-[15px] text-[#1a1a1a] dark:text-white placeholder-[#999] max-h-[160px] custom-scrollbar leading-relaxed"
              :placeholder="copy.inputPlaceholder"
              @keydown.enter.meta.prevent="handleSend"
              @keydown.enter.ctrl.prevent="handleSend"
              @input="resizeTextarea"
              style="min-height: 52px"
            />

            <!-- Popover Overlay -->
            <div
              v-if="showFilePopover"
              @click="hideFilePopover"
              class="fixed inset-0 z-[90]"
            ></div>

            <!-- Tools Row -->
            <div
              class="flex items-center justify-between px-3 py-2 relative z-[100] border-t border-transparent"
            >
              <div class="flex items-center gap-1.5 relative flex-wrap">
                <!-- Mode Indicator Tag: Hide when viewing existing chat to keep layout clean -->
                <div
                  v-if="!isUserClearedMode && !hasConversation"
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 text-[13px] font-medium border border-blue-100 dark:border-blue-500/20 shadow-sm cursor-default"
                >
                  <LucideIcon
                    :name="
                      activeMode === 'script'
                        ? 'Captions'
                        : activeMode === 'remake'
                          ? 'Video'
                          : 'Sparkles'
                    "
                    class="w-4 h-4 ml-0.5"
                  />
                  <span>{{
                    activeMode === "script"
                      ? "视频分析"
                      : activeMode === "remake"
                        ? "复刻爆款"
                        : "创作爆款"
                  }}</span>
                  <button
                    @click="handleClearMode"
                    class="hover:bg-blue-200 dark:hover:bg-blue-500/30 rounded-full p-0.5 ml-1 transition-colors"
                  >
                    <LucideIcon name="X" class="w-3.5 h-3.5" />
                  </button>
                </div>

                <div
                  v-if="!isUserClearedMode && !hasConversation"
                  class="w-[1px] h-4 bg-slate-200 dark:bg-white/10 mx-2"
                ></div>

                <!-- Attachment Buttons -->
                <button
                  @click="handleUploadClick"
                  :disabled="selectedUrls.length > 0"
                  class="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 rounded-full transition-colors text-[13px]"
                  :class="
                    selectedUrls.length > 0
                      ? 'opacity-50 cursor-not-allowed'
                      : ''
                  "
                >
                  <LucideIcon
                    name="Paperclip"
                    class="w-[18px] h-[18px]"
                    stroke-width="1.8"
                  />
                  <span>{{ uploadButtonLabel }}</span>
                </button>

                <button
                  v-if="isRemakeSubmission"
                  @click="handleAudioUploadClick"
                  class="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 rounded-full transition-colors text-[13px]"
                >
                  <LucideIcon
                    name="Music"
                    class="w-[18px] h-[18px]"
                    stroke-width="1.8"
                  />
                  <span>上传音频</span>
                </button>

                <button
                  @click="handleAddLinkClick"
                  :disabled="selectedFile !== null || isRemakeSubmission"
                  class="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 rounded-full transition-colors text-[13px]"
                  :class="
                    selectedFile || isRemakeSubmission
                      ? 'opacity-50 cursor-not-allowed'
                      : ''
                  "
                >
                  <LucideIcon
                    name="Link"
                    class="w-[18px] h-[18px]"
                    stroke-width="1.8"
                  />
                  <span>添加链接</span>
                </button>
              </div>

              <!-- Right Actions (Mic & Send) -->
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
    </main>

    <input
      ref="fileInputRef"
      class="hidden"
      type="file"
      :accept="currentUploadAccept"
      @change="handleFileChange"
    />
    <input
      ref="audioInputRef"
      class="hidden"
      type="file"
      :accept="remakeAudioAccept"
      @change="handleAudioFileChange"
    />

    <InputPromptModal
      :open="renamingProjectId !== null"
      title="编辑对话名称"
      :value="renameDraft"
      :error="renameModalError"
      :pending="renamingProjectPending"
      confirm-text="确定"
      cancel-text="取消"
      :select-on-open="true"
      @close="cancelRenameProject"
      @confirm="submitCurrentRenameProject"
      @update:value="renameDraft = $event"
    />

    <InputPromptModal
      :open="showLinkModal"
      title="添加链接"
      description="粘贴一个视频或网页链接，作为分析或素材参考"
      :value="linkDraft"
      :error="linkModalError"
      :pending="false"
      input-type="url"
      placeholder="https://www.tiktok.com/@..."
      helper="支持 http/https 链接；添加后会作为附件显示"
      confirm-text="添加"
      cancel-text="取消"
      :select-on-open="false"
      @close="closeLinkModal"
      @confirm="confirmLinkModal"
      @update:value="linkDraft = $event"
    />

    <!-- 退出登录确认弹窗 -->
    <ConfirmModal
      v-model="showLogoutModal"
      title="确认退出登录"
      message="您确定要退出当前账号吗？"
      confirmText="确认退出"
      @confirm="confirmLogout"
      @cancel="cancelLogout"
    />

    <!-- 删除确认弹窗 -->
    <ConfirmModal
      :modelValue="!!projectToDelete"
      @update:modelValue="
        (val) => {
          if (!val) cancelDeleteProject();
        }
      "
      title="确认删除对话"
      message="确认删除此对话吗？删除后无法恢复。"
      confirmText="确认删除"
      :loading="!!(projectToDelete && deletingProjectId === projectToDelete.id)"
      @confirm="confirmDeleteProject"
      @cancel="cancelDeleteProject"
    />

    <!-- 查看文件 (Video details) Modal -->
    <div
      v-if="showVideoDetailModal"
      class="fixed inset-0 z-[150] flex items-center justify-end bg-black/20 sm:p-4"
      @click.self="showVideoDetailModal = false"
    >
      <div
        class="w-full h-full sm:h-auto sm:max-h-full sm:w-[460px] bg-white dark:bg-[#121212] sm:rounded-2xl shadow-xl flex flex-col overflow-hidden animate-in slide-in-from-right sm:fade-in-0 sm:zoom-in-95"
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between px-4 py-3 sm:py-4 border-b border-[#eee] dark:border-white/10 shrink-0"
        >
          <div class="flex items-center gap-2 min-w-0 pr-4">
            <LucideIcon
              name="Video"
              class="w-[18px] h-[18px] shrink-0 text-[#1a1a1a] dark:text-white"
            />
            <h3
              class="text-[16px] font-bold text-[#1a1a1a] dark:text-white truncate"
            >
              {{ selectedProject?.title || "视频详情" }}
            </h3>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button
              @click="showVideoDetailModal = false"
              class="w-8 h-8 flex items-center justify-center rounded-full text-[#666] hover:bg-[#f3f4f6] dark:hover:bg-white/10 transition-colors"
            >
              <LucideIcon name="X" class="w-[18px] h-[18px]" />
            </button>
          </div>
        </div>

        <!-- Body -->
        <div
          class="flex-1 overflow-y-auto bg-[#fafafa] dark:bg-[#1a1a1a] custom-scrollbar"
        >
          <!-- Video Section -->
          <div class="p-4 bg-white dark:bg-[#121212]">
            <div
              class="w-full aspect-[9/16] max-h-[360px] bg-black rounded-xl overflow-hidden flex items-center justify-center relative shadow-sm"
            >
              <video
                v-if="selectedProjectPreviewUrl"
                :src="selectedProjectPreviewUrl"
                controls
                class="w-full h-full object-contain"
              ></video>
              <div
                v-else
                class="text-white/50 text-[13px] flex flex-col items-center gap-2"
              >
                <LucideIcon name="PlayCircle" class="w-8 h-8 opacity-50" />
                <span>正在提取或无法预览视频</span>
              </div>
            </div>
            <div class="mt-3 flex flex-col items-center gap-2 text-center">
              <a
                v-if="selectedProjectPreviewUrl"
                :href="selectedProjectPreviewUrl"
                target="_blank"
                class="inline-flex items-center gap-1.5 text-[13px] text-blue-600 hover:underline break-all mx-auto max-w-[90%]"
                title="打开可播放视频"
              >
                <span class="truncate">打开可播放视频文件</span>
                <LucideIcon name="ExternalLink" class="w-3.5 h-3.5 shrink-0" />
              </a>
              <a
                v-if="selectedProjectSourcePageUrl"
                :href="selectedProjectSourcePageUrl"
                target="_blank"
                class="inline-flex items-center gap-1.5 text-[13px] text-[#6b7280] dark:text-[#9ca3af] hover:text-[#1a1a1a] dark:hover:text-white transition-colors break-all mx-auto max-w-[90%]"
                title="在浏览器中打开"
              >
                <span class="truncate">{{
                  selectedProjectSourcePageUrl || selectedProject?.source_name
                }}</span>
                <LucideIcon name="ExternalLink" class="w-3.5 h-3.5 shrink-0" />
              </a>
            </div>
          </div>

          <!-- Tabs -->
          <div
            class="px-4 py-2 bg-white dark:bg-[#121212] sticky top-0 z-10 border-b border-[#eee] dark:border-white/10 shadow-[0_2px_4px_rgba(0,0,0,0.02)]"
          >
            <div
              class="flex items-center gap-2 p-1 bg-[#f1f2f4] dark:bg-white/5 rounded-xl"
            >
              <button
                @click="activeDetailTab = 'analysis'"
                class="flex-1 py-1.5 text-[14px] font-medium rounded-lg transition-all flex items-center justify-center gap-1.5"
                :class="
                  activeDetailTab === 'analysis'
                    ? 'bg-white dark:bg-[#262626] text-[#1a1a1a] dark:text-white shadow-sm'
                    : 'text-[#666] dark:text-[#aaa] hover:text-[#1a1a1a] dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5'
                "
              >
                <LucideIcon name="Sparkles" class="w-[15px] h-[15px]" />
                分析
              </button>
              <button
                @click="activeDetailTab = 'timeline'"
                class="flex-1 py-1.5 text-[14px] font-medium rounded-lg transition-all flex items-center justify-center gap-1.5"
                :class="
                  activeDetailTab === 'timeline'
                    ? 'bg-white dark:bg-[#262626] text-[#1a1a1a] dark:text-white shadow-sm'
                    : 'text-[#666] dark:text-[#aaa] hover:text-[#1a1a1a] dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5'
                "
              >
                <LucideIcon name="ScrollText" class="w-[15px] h-[15px]" />
                时间轴
              </button>
              <button
                v-if="hasVisibleRemakeGeneration"
                @click="activeDetailTab = 'generation'"
                class="flex-1 py-1.5 text-[14px] font-medium rounded-lg transition-all flex items-center justify-center gap-1.5"
                :class="
                  activeDetailTab === 'generation'
                    ? 'bg-white dark:bg-[#262626] text-[#1a1a1a] dark:text-white shadow-sm'
                    : 'text-[#666] dark:text-[#aaa] hover:text-[#1a1a1a] dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5'
                "
              >
                <LucideIcon name="Clapperboard" class="w-[15px] h-[15px]" />
                复刻
              </button>
            </div>
          </div>

          <!-- Content -->
          <div class="p-4 space-y-3 pb-8">
            <!-- Analysis Tab -->
            <template v-if="activeDetailTab === 'analysis'">
              <div
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="Sparkles"
                    class="w-[16px] h-[16px] text-purple-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    {{ analysisPanelTitle }}
                  </div>
                </div>
                <template
                  v-if="
                    selectedProject?.workflow_type === 'remake' &&
                    hasStructuredRemakeAnalysis
                  "
                >
                  <div
                    v-if="remakeAnalysisSummary"
                    class="text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                  >
                    {{ remakeAnalysisSummary }}
                  </div>

                  <div v-if="remakeAdviceCards.length > 0" class="mt-3 grid gap-3">
                    <div
                      v-for="card in remakeAdviceCards"
                      :key="card.title"
                      class="rounded-xl border border-[#eee] bg-[#fafafa] px-3.5 py-3 dark:border-white/10 dark:bg-white/5"
                    >
                      <div class="text-[12px] text-[#999] dark:text-[#aaa]">
                        {{ card.title }}
                      </div>
                      <div
                        class="mt-1 text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                      >
                        {{ card.body }}
                      </div>
                    </div>
                  </div>

                  <div v-if="remakeScriptCards.length > 0" class="mt-3 grid gap-3">
                    <div
                      v-for="item in remakeScriptCards"
                      :key="`${item.title}-${item.timing}`"
                      class="rounded-xl border border-[#eee] bg-[#fafafa] px-3.5 py-3 dark:border-white/10 dark:bg-white/5"
                    >
                      <div
                        class="flex flex-wrap items-center gap-2 text-[13px] font-medium text-[#1a1a1a] dark:text-white"
                      >
                        <span>{{ item.title }}</span>
                        <span
                          v-if="item.timing"
                          class="rounded-full border border-[#eee] px-2 py-0.5 text-[12px] font-mono text-[#666] dark:border-white/10 dark:text-[#aaa]"
                        >
                          {{ item.timing }}
                        </span>
                      </div>
                      <div class="mt-2 space-y-1.5 text-[14px] leading-relaxed">
                        <div class="text-[#1a1a1a] dark:text-white">
                          口播：{{ item.voiceover }}
                        </div>
                        <div class="text-[#666] dark:text-[#aaa]">
                          字幕：{{ item.subtitle }}
                        </div>
                        <div class="text-[#666] dark:text-[#aaa]">
                          镜头：{{ item.direction }}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="mt-3 rounded-xl border border-[#eee] bg-[#fafafa] px-3.5 py-3 dark:border-white/10 dark:bg-white/5">
                    <div class="text-[12px] text-[#999] dark:text-[#aaa]">
                      万相生成方案
                    </div>
                    <div
                      class="mt-1 whitespace-pre-wrap text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                    >
                      {{ remakeWanxiangPrompt }}
                    </div>
                    <ul
                      v-if="remakeWanxiangNotes.length > 0"
                      class="mt-3 space-y-2 pl-5 text-[13px] text-[#666] dark:text-[#aaa]"
                    >
                      <li v-for="note in remakeWanxiangNotes" :key="note">
                        {{ note }}
                      </li>
                    </ul>
                  </div>
                </template>

                <div
                  v-else
                  class="whitespace-pre-wrap text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                  :class="
                    ecommerceAnalysisLooksFailed
                      ? 'text-rose-600 dark:text-rose-300'
                      : ''
                  "
                >
                  {{
                    selectedProject?.ecommerce_analysis?.content ||
                    (selectedProject?.status === "ready"
                      ? analysisEmptyReadyMessage
                      : analysisProcessingMessage)
                  }}
                </div>
              </div>

              <div
                v-if="hasVisibleSourceAnalysis"
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="ImagePlus"
                    class="w-[16px] h-[16px] text-amber-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    关键帧与视觉特征
                  </div>
                </div>

                <div
                  v-if="sourceVisualFeatures?.summary"
                  class="text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                >
                  {{ sourceVisualFeatures.summary }}
                </div>

                <div
                  v-if="sourceVisualMetaBadges.length > 0"
                  class="mt-3 flex flex-wrap gap-2"
                >
                  <span
                    v-for="badge in sourceVisualMetaBadges"
                    :key="badge.label"
                    class="rounded-full border border-[#eee] bg-[#f8f9fa] px-3 py-1.5 text-[12px] text-[#666] dark:border-white/10 dark:bg-white/5 dark:text-[#aaa]"
                  >
                    {{ badge.label }} · {{ badge.value }}
                  </span>
                </div>

                <div
                  v-if="sourceVisualSignalCards.length > 0"
                  class="mt-3 grid gap-3"
                >
                  <div
                    v-for="card in sourceVisualSignalCards"
                    :key="card.label"
                    class="rounded-xl border border-[#eee] bg-[#fafafa] px-3.5 py-3 dark:border-white/10 dark:bg-white/5"
                  >
                    <div class="text-[12px] text-[#999] dark:text-[#aaa]">
                      {{ card.label }}
                    </div>
                    <div
                      class="mt-1 text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                    >
                      {{ card.value }}
                    </div>
                  </div>
                </div>

                <div
                  v-if="sourceVisualFeatures?.dominant_palette?.length"
                  class="mt-3 flex flex-wrap gap-2"
                >
                  <div
                    v-for="color in sourceVisualFeatures.dominant_palette"
                    :key="color"
                    class="flex items-center gap-2 rounded-full border border-[#eee] bg-[#fafafa] px-3 py-2 dark:border-white/10 dark:bg-white/5"
                  >
                    <span
                      class="h-4 w-4 rounded-full border border-black/10"
                      :style="{ backgroundColor: color }"
                    />
                    <span
                      class="font-mono text-[12px] text-[#666] dark:text-[#aaa]"
                    >
                      {{ color }}
                    </span>
                  </div>
                </div>

                <div v-if="sourceReferenceFrames.length > 0" class="mt-3">
                  <div class="grid grid-cols-2 gap-3">
                    <img
                      v-for="(frame, index) in sourceReferenceFrames"
                      :key="`${index}-${frame.slice(0, 32)}`"
                      :src="frame"
                      :alt="`对标关键帧 ${index + 1}`"
                      class="aspect-[9/16] w-full rounded-xl border border-[#eee] object-cover dark:border-white/10"
                    />
                  </div>
                </div>
              </div>

              <div
                v-if="selectedProject?.script_overview?.full_text"
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="Text"
                    class="w-[16px] h-[16px] text-blue-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    字幕整理
                  </div>
                </div>
                <div
                  class="whitespace-pre-wrap text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                >
                  {{ selectedProject.script_overview.full_text }}
                </div>
              </div>
            </template>

            <!-- Timeline Tab -->
            <template v-if="activeDetailTab === 'timeline'">
              <div
                v-for="segment in selectedProject?.timeline_segments"
                :key="segment.id"
                class="bg-white dark:bg-[#262626] rounded-xl p-3.5 border border-[#eee] dark:border-white/5 shadow-sm text-[#1a1a1a] dark:text-white text-[14px] flex gap-3 hover:border-[#ddd] dark:hover:border-white/10 transition-colors group"
              >
                <div
                  class="text-[13px] font-mono font-medium text-[#666] dark:text-[#aaa] shrink-0 pt-[1.5px] w-[95px] whitespace-nowrap"
                >
                  {{ formatRange(segment.start_ms, segment.end_ms) }}
                </div>
                <div class="flex-1 leading-relaxed">
                  <span
                    v-if="segment.speaker"
                    class="font-semibold text-blue-600 dark:text-blue-400 mr-2"
                    >{{ segment.speaker }}:</span
                  >
                  {{ segment.content }}
                </div>
              </div>

              <div
                v-if="!selectedProject?.timeline_segments?.length"
                class="text-[14px] text-[#999] text-center py-10 my-4 bg-white dark:bg-[#262626] rounded-xl border border-[#eee] dark:border-white/5"
              >
                <LucideIcon
                  name="FileQuestion"
                  class="w-8 h-8 mx-auto mb-2 opacity-20"
                />
                暂无时间轴内容
              </div>
            </template>

            <template v-if="activeDetailTab === 'generation'">
              <div
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div class="flex flex-wrap items-center gap-2">
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    视频复刻状态
                  </div>
                  <span
                    class="rounded-full border px-2.5 py-1 text-[12px] font-medium"
                    :class="
                      getRemakeGenerationStatusClass(
                        remakeGeneration?.status || 'idle',
                      )
                    "
                  >
                    {{
                      getRemakeGenerationStatusLabel(
                        remakeGeneration?.status || "idle",
                      )
                    }}
                  </span>
                </div>

                <div
                  class="mt-3 space-y-2 text-[14px] text-[#1a1a1a] dark:text-white"
                >
                  <div v-if="remakeGenerationProviderLabel">
                    Provider: {{ remakeGenerationProviderLabel }}
                  </div>
                  <div v-if="remakeGeneration?.model">
                    Model: {{ remakeGeneration.model }}
                  </div>
                  <div v-if="remakeGeneration?.asset_name">
                    素材：{{ remakeGeneration.asset_name }}
                    <span class="text-[#666] dark:text-[#aaa]">
                      （{{
                        remakeGeneration.asset_type === "image"
                          ? "图片"
                          : remakeGeneration.asset_type === "video"
                            ? "视频"
                            : "文生视频"
                      }}）
                    </span>
                  </div>
                  <div v-if="remakeGeneration?.audio_name">
                    配音：{{ remakeGeneration.audio_name }}
                  </div>
                  <div
                    v-if="remakeGeneration?.provider_task_id"
                    class="break-all font-mono text-[12px] text-[#666] dark:text-[#aaa]"
                  >
                    Task ID: {{ remakeGeneration.provider_task_id }}
                  </div>
                </div>

                <div v-if="remakeGeneration?.result_video_url" class="mt-4">
                  <video
                    :src="remakeGeneration.result_video_url"
                    controls
                    class="w-full rounded-xl border border-[#eee] bg-black dark:border-white/10"
                  ></video>
                </div>

                <div v-if="remakeGeneration?.audio_url" class="mt-4">
                  <audio
                    :src="remakeGeneration.audio_url"
                    controls
                    class="w-full"
                  ></audio>
                </div>

                <div
                  v-if="remakeGeneration?.error_detail"
                  class="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200"
                >
                  {{ remakeGeneration.error_detail }}
                </div>
              </div>

              <div
                v-if="remakeReferenceFrames.length > 0"
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="Image"
                    class="w-[16px] h-[16px] text-amber-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    抽帧参考
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <img
                    v-for="(frame, index) in remakeReferenceFrames"
                    :key="`${index}-${frame.slice(0, 32)}`"
                    :src="frame"
                    :alt="`参考帧 ${index + 1}`"
                    class="aspect-[9/16] w-full rounded-xl border border-[#eee] object-cover dark:border-white/10"
                  />
                </div>
              </div>

              <div
                v-if="remakeGeneration?.script"
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="FileText"
                    class="w-[16px] h-[16px] text-blue-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    生成脚本
                  </div>
                </div>
                <div
                  class="whitespace-pre-wrap text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                >
                  {{ remakeGeneration.script }}
                </div>
              </div>

              <div
                v-if="remakeGeneration?.storyboard"
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="Clapperboard"
                    class="w-[16px] h-[16px] text-amber-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    生成分镜
                  </div>
                </div>
                <div
                  class="whitespace-pre-wrap text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                >
                  {{ remakeGeneration.storyboard }}
                </div>
              </div>

              <div
                v-if="remakeGeneration?.prompt"
                class="bg-white dark:bg-[#262626] rounded-2xl p-4 border border-[#eee] dark:border-white/5 shadow-sm"
              >
                <div
                  class="mb-3 flex items-center gap-2 border-b border-[#eee] dark:border-white/5 pb-2"
                >
                  <LucideIcon
                    name="Sparkles"
                    class="w-[16px] h-[16px] text-violet-500"
                  />
                  <div
                    class="font-bold text-[15px] text-[#1a1a1a] dark:text-white"
                  >
                    {{
                      remakeGeneration?.provider === "qwen"
                        ? "万相生成提示词"
                        : "生成提示词"
                    }}
                  </div>
                </div>
                <div
                  class="whitespace-pre-wrap break-words text-[14px] leading-relaxed text-[#1a1a1a] dark:text-white"
                >
                  {{ remakeGeneration.prompt }}
                </div>
              </div>
            </template>
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
