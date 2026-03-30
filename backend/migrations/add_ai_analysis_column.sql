-- 添加 ai_analysis 字段到 video_project 表
ALTER TABLE os_video_project
ADD COLUMN ai_analysis TEXT NULL;
