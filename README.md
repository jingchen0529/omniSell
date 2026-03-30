# OmniSell

OmniSell 是一个电商场景的 AI 视频分析与创作工作台，当前仓库包含：

- 后端：`Python 3.10+`、`FastAPI`、`SQLAlchemy`、`PyMySQL`
- 前端：`Nuxt 3`、`Vue 3`、`Tailwind CSS v4`
- 视频能力：`ffmpeg`、`ffprobe`、`yt-dlp`、`faster-whisper`
- 任务处理：开发环境默认内嵌 worker，也支持单独启动 worker 进程

## 目录结构

```text
omniSell/
├── backend/      # FastAPI 后端
├── frontend/     # Nuxt 3 前端
├── Makefile      # 常用启动命令
├── .gitignore
└── README.md
```

## 运行前需要安装什么

### 1. 系统环境

请先安装这些基础环境：

- `Python 3.10` 或更高版本
- `Node.js` 与 `npm`
- `MySQL`，默认连接本地 `127.0.0.1:3306`
- `ffmpeg`
- `ffprobe`
- `yt-dlp`

说明：

- 后端默认数据库名是 `omni-sell`
- 后端启动时会自动尝试创建数据库和初始化表
- 如果使用本地 `faster-whisper`，首次运行会自动下载模型到 `backend/storage/models`

### 1.1 安装 `yt-dlp`

项目里视频下载依赖系统里的 `yt-dlp` 可执行文件，后端默认读取的是：

```env
YT_DLP_BINARY=yt-dlp
```

常见安装方式：

macOS（Homebrew）：

```bash
brew install yt-dlp
```

或使用 Python 安装：

```bash
python3 -m pip install -U yt-dlp
```

安装完成后可以检查一下：

```bash
yt-dlp --version
```

如果你是用 `pip` 装的，但终端里找不到 `yt-dlp` 命令，需要把 Python 的 scripts/bin 目录加入 `PATH`，或者把 `backend/.env` 里的 `YT_DLP_BINARY` 改成实际可执行文件路径。

### 2. 后端 Python 依赖

后端依赖已经写在下面两个文件里：

- `backend/requirements.txt`：运行依赖
- `backend/requirements-dev.txt`：开发依赖，额外包含 `pytest`、`ruff`、`httpx`

安装命令：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

后端主要会安装这些包：

- `fastapi`
- `uvicorn[standard]`
- `sqlalchemy`
- `pymysql`
- `pydantic`
- `pydantic-settings`
- `python-multipart`
- `python-dotenv`
- `faster-whisper`
- `openai`
- `pytest`
- `ruff`

### 3. 前端依赖、模块和插件

前端依赖都已经写在 `frontend/package.json` 中，执行一次 `npm install` 就会自动安装，不需要再单独全局安装 Nuxt 或 UI 插件。

安装命令：

```bash
cd frontend
npm install
```

前端主要依赖 / 模块如下：

- `nuxt`
- `@nuxtjs/i18n`
- `shadcn-nuxt`
- `@tailwindcss/vite`
- `tailwindcss`
- `sass`
- `@vueuse/core`
- `reka-ui`
- `lucide-vue-next`

### 4. 可选的 AI 能力

如果你要用 OpenAI 兼容接口做转写或聊天能力，还需要配置：

- `OPENAI_API_BASE`
- `OPENAI_API_KEY`

不配置也能跑，只是部分 AI 能力会受影响。默认视频转写走本地 `faster-whisper`。

## 环境变量

### 后端环境变量

先复制示例文件：

```bash
cd backend
cp .env.example .env
```

最常用的配置如下：

```env
APP_ENV=development
API_PREFIX=/api
CORS_ORIGINS=["http://localhost:3000"]

DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=
DATABASE_NAME=omni-sell

VIDEO_ANALYSIS_PROVIDER=real
VIDEO_TRANSCRIPTION_PROVIDER=faster_whisper
VIDEO_TRANSCRIPTION_LANGUAGE=zh

FFMPEG_BINARY=ffmpeg
FFPROBE_BINARY=ffprobe
YT_DLP_BINARY=yt-dlp
```

常见可选项：

- `DATABASE_URL`：直接覆盖数据库连接串
- `OPENAI_API_BASE`
- `OPENAI_API_KEY`
- `OPENAI_AUDIO_MODEL`
- `OPENAI_CHAT_MODEL`
- `PROJECT_JOB_RUN_EMBEDDED_WORKER`

### 前端环境变量

先复制示例文件：

```bash
cd frontend
cp .env.example .env
```

默认只需要配置后端接口地址：

```env
NUXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api
```

## 前后端怎么运行

### 方式一：按命令分别启动

#### 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

默认地址：

- API：`http://127.0.0.1:8000`
- Swagger 文档：`http://127.0.0.1:8000/docs`

开发环境下，后端默认会自动启动内嵌 worker 线程处理项目任务，所以大多数情况下只开 `uvicorn` 就够了。

如果你想单独启动 worker，可以再开一个终端：

```bash
cd backend
source .venv/bin/activate
python -m app.worker
```

#### 启动前端

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

默认地址：

- Web：`http://127.0.0.1:3000`

### 方式二：使用 Makefile

根目录已经提供了常用命令：

```bash
make backend-install
make backend-dev
make backend-worker
make frontend-install
make frontend-dev
```

对应作用：

- `make backend-install`：创建后端虚拟环境并安装依赖
- `make backend-dev`：启动 FastAPI 开发服务
- `make backend-worker`：启动独立 worker
- `make frontend-install`：安装前端依赖
- `make frontend-dev`：启动 Nuxt 开发服务

## 前端脚本

`frontend/package.json` 里已经定义好了这些脚本：

```bash
npm run dev
npm run build
npm run start
npm run preview
```

含义如下：

- `npm run dev`：本地开发
- `npm run build`：构建生产包
- `npm run start`：启动构建后的服务
- `npm run preview`：本地预览生产构建结果

## 默认账号

开发环境默认会创建一个演示账号：

- 邮箱：`demo@omnisell.local`
- 密码：`demo123456`

## 备注

- 前端请求后端地址来自 `frontend/.env` 中的 `NUXT_PUBLIC_API_BASE`
- 后端默认允许 `http://localhost:3000` 跨域访问
- 如果视频链接没有现成字幕，后端会尝试转写音频
- `backend/storage/uploads`、`backend/storage/runtime`、`backend/storage/models` 都属于本地运行时目录，通常不应提交到仓库
