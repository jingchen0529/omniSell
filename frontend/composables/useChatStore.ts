import { useState } from '#app';

export type ModeTab = "script" | "remake" | "create";
export type ProjectWorkflowType = "analysis" | "create" | "remake";

export interface ProjectListItem {
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

export interface ProjectTaskStep {
  id: number;
  step_key: string;
  title: string;
  detail: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  error_detail: string | null;
  display_order: number;
  updated_at: string;
}

export interface ProjectVideoGeneration {
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

export interface ProjectSourceVisualFeatures {
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

export interface ProjectSourceAnalysis {
  reference_frames: string[];
  visual_features: ProjectSourceVisualFeatures | null;
}

export interface ProjectDetail extends ProjectListItem {
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

export interface AssistantFeedback {
  status: "pending" | "error";
  objective: string;
  sourceLabel: string;
  message: string;
}

export const useChatStore = () => {
  const projects = useState<ProjectListItem[]>('chat_projects', () => []);
  const loadingHistory = useState<boolean>('chat_loading_history', () => false);
  const selectedProject = useState<ProjectDetail | null>('chat_selected_project', () => null);
  const activeMode = useState<ModeTab>('chat_active_mode', () => 'script');
  
  return {
    projects,
    loadingHistory,
    selectedProject,
    activeMode
  };
};
