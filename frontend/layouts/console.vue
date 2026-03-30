<script setup lang="ts">
import ConfirmModal from "~/components/custom/ConfirmModal.vue";
import InputPromptModal from "~/components/custom/InputPromptModal.vue";
import { Toaster } from "~/components/ui/sonner";
import { useRoute, useRouter } from "vue-router";
import { ref, onMounted, onUnmounted, computed } from "vue";

const { locale, setLocale, t } = useI18n();
const { themePref, isDark, setTheme } = useTheme();

const auth = useAuth();
const api = useOmniSellApi();
const chatStore = useChatStore();
const router = useRouter();
const route = useRoute();
const logoutLoading = ref(false);

const historyProjects = chatStore.projects;
const loadingHistory = chatStore.loadingHistory;
const selectedProject = chatStore.selectedProject;
const renamingProjectId = ref<number | null>(null);
const renameDraft = ref("");
const renameModalError = ref("");
const renamingProjectPending = ref(false);
const deletingProjectId = ref<number | null>(null);
const projectToDelete = ref<(typeof historyProjects.value)[number] | null>(
  null,
);

const handleLogout = async () => {
  logoutLoading.value = true;
  await auth.logout();
  logoutLoading.value = false;
  await router.push("/auth/login");
};

const goToSystemSettings = async () => {
  isUserMenuOpen.value = false;
  activeSubmenu.value = null;
  await router.push({
    path: "/settings/system",
    query: route.query.projectId
      ? {
          projectId: String(route.query.projectId),
        }
      : undefined,
  });
};

// Sidebar collapse
const isSidebarCollapsed = ref(false);
const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
};

// Submenu
const activeSubmenu = ref<string | null>(null);

// User Menu Toggle
const isUserMenuOpen = ref(false);
const toggleUserMenu = (e: MouseEvent) => {
  e.stopPropagation();
  isUserMenuOpen.value = !isUserMenuOpen.value;
};

const closeUserMenu = (e: Event) => {
  const container = document.getElementById("user-menu-container");
  if (container && !container.contains(e.target as Node)) {
    isUserMenuOpen.value = false;
    activeSubmenu.value = null;
  }
};

const ensureHistoryProjectsLoaded = async () => {
  if (loadingHistory.value || historyProjects.value.length > 0) {
    return;
  }

  loadingHistory.value = true;
  try {
    historyProjects.value = await api("/projects");
  } catch (error) {
    console.error("Failed to load sidebar history:", error);
  } finally {
    loadingHistory.value = false;
  }
};

onMounted(() => {
  document.addEventListener("click", closeUserMenu);
  void ensureHistoryProjectsLoaded();
});

onUnmounted(() => {
  document.removeEventListener("click", closeUserMenu);
});

const menuItems = [
  { name: "新对话", path: "/new-chat", icon: "MessageSquarePlus" as const },
  // { name: "分析脚本", path: "/analysis", icon: "FileText" as const },
  // { name: "复刻爆款", path: "/repurpose", icon: "Copy" as const },
  // { name: "创作爆款", path: "/creation", icon: "Lightbulb" as const },
];

const isCurrent = (path: string) => {
  if (path === "/") {
    return route.path === "/";
  }
  return route.path.startsWith(path);
};

const currentRouteName = computed(() => {
  // Only show project title if we are actively viewing a project on the new-chat page
  if (
    selectedProject.value &&
    route.path === "/new-chat" &&
    route.query.projectId
  ) {
    return selectedProject.value.title;
  }
  const item = menuItems.find((m) => isCurrent(m.path));
  if (item) {
    return item.name;
  }
  if (route.path.startsWith("/settings/system")) {
    return "系统设置";
  }
  return "";
});

const filteredHistoryProjects = computed(() => historyProjects.value);

const activeHistoryProjectId = computed(() =>
  Number(route.query.projectId ?? 0),
);

const openHistoryProject = async (projectId: number) => {
  await router.push({
    path: "/new-chat",
    query: {
      projectId: String(projectId),
    },
  });
};

const startRenameProject = (
  project: (typeof historyProjects.value)[number],
) => {
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
  historyProjects.value = historyProjects.value.map((project) =>
    project.id === projectId ? { ...project, title } : project,
  );

  if (selectedProject.value?.id === projectId) {
    selectedProject.value = {
      ...selectedProject.value,
      title,
    };
  }
};

const submitRenameProject = async () => {
  if (renamingProjectId.value === null || renamingProjectPending.value) {
    return;
  }

  const title = renameDraft.value.trim();
  if (!title) {
    renameModalError.value = "标题不能为空";
    return;
  }

  renamingProjectPending.value = true;
  try {
    const updatedProject = await api<typeof selectedProject.value>(
      `/projects/${renamingProjectId.value}`,
      {
        method: "PATCH",
        body: { title },
      },
    );
    applyProjectTitleLocally(
      renamingProjectId.value,
      updatedProject?.title || title,
    );
    cancelRenameProject();
  } catch (error: any) {
    renameModalError.value =
      error?.data?.detail || error?.message || "重命名失败";
  } finally {
    renamingProjectPending.value = false;
  }
};

const deleteProject = (project: (typeof historyProjects.value)[number]) => {
  projectToDelete.value = project;
};

const cancelDeleteProject = () => {
  projectToDelete.value = null;
};

const confirmDeleteProject = async () => {
  const project = projectToDelete.value;
  if (!project || deletingProjectId.value === project.id) {
    return;
  }

  deletingProjectId.value = project.id;
  try {
    await api(`/projects/${project.id}`, {
      method: "DELETE",
    });

    historyProjects.value = historyProjects.value.filter(
      (item) => item.id !== project.id,
    );

    if (
      selectedProject.value?.id === project.id ||
      activeHistoryProjectId.value === project.id
    ) {
      selectedProject.value = null;
      const fallbackProject =
        historyProjects.value[0] || null;
      await router.replace({
        path: route.path,
        query: fallbackProject
          ? {
              ...route.query,
              projectId: String(fallbackProject.id),
            }
          : Object.fromEntries(
              Object.entries(route.query).filter(
                ([key]) => key !== "projectId",
              ),
            ),
      });
    }

    if (renamingProjectId.value === project.id) {
      cancelRenameProject();
    }
    cancelDeleteProject();
  } catch (error) {
    console.error(error);
  } finally {
    deletingProjectId.value = null;
  }
};

const localeOptions = [
  { code: "en", label: "English" },
  { code: "ja", label: "日本語" },
  { code: "tw", label: "繁體中文" },
  { code: "zh", label: "简体中文" },
];

const switchLocale = (code: string) => {
  setLocale(code as any);
};

const isItemActive = (item: any) => {
  const projId = route.query.projectId;
  const hasProject = !!projId;
  const isNewChatRoute = route.path === "/new-chat";

  // 1. "New Chat" logic: Only when on route and NO project loaded (or project cleared)
  if (item.path === "/new-chat") {
    return (
      (isNewChatRoute && !hasProject) ||
      (isNewChatRoute && hasProject && !selectedProject.value)
    );
  }

  // 2. Direct page match: If we are on /analysis or /creation pages themselves
  if (route.path === item.path) {
    return true;
  }

  // 3. Project context matching: If we are on /new-chat with a project, highlight the parent category
  if (isNewChatRoute && hasProject && selectedProject.value) {
    const type = selectedProject.value.workflow_type;
    if (item.path === "/analysis" && type === "analysis") return true;
    if (item.path === "/repurpose" && type === "remake") return true;
    if (item.path === "/creation" && type === "create") return true;
  }

  return false;
};
</script>

<template>
  <div
    class="flex h-screen w-full overflow-hidden bg-[#ffffff] dark:bg-[#171717] text-slate-900 dark:text-slate-100 transition-colors duration-300"
  >
    <!-- Sidebar -->
    <aside
      class="flex flex-col border-r border-slate-200 dark:border-white/10 bg-[#f5f5f5] dark:bg-[#262626] transition-all duration-300 z-[150]"
      :class="isSidebarCollapsed ? 'w-[72px]' : 'w-[260px]'"
    >
      <!-- Logo -->
      <div
        class="flex h-14 shrink-0 items-center overflow-hidden transition-all duration-300 border-b border-transparent"
        :class="isSidebarCollapsed ? 'px-0 justify-center' : 'px-6'"
      >
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-[#ff6a00] text-white shrink-0"
        >
          <LucideIcon name="Boxes" class="h-6 w-6" :stroke-width="2" />
        </div>
        <span
          v-if="!isSidebarCollapsed"
          class="ml-3 text-lg font-bold tracking-tight text-slate-900 dark:text-white whitespace-nowrap"
          >爆款杀手🥷</span
        >
      </div>

      <!-- Navigation -->
      <nav
        class="flex-1 space-y-1 py-4 overflow-y-auto"
        :class="isSidebarCollapsed ? 'px-2' : 'px-3'"
      >
        <div
          v-if="!isSidebarCollapsed"
          class="mb-2 px-3 text-xs font-semibold text-slate-400 dark:text-slate-500 whitespace-nowrap"
        >
          主导航
        </div>
        <NuxtLink
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          active-class=""
          inactive-class=""
          class="group flex items-center py-2.5 text-sm font-medium rounded-xl transition-all"
          :class="[
            isSidebarCollapsed ? 'justify-center px-0' : 'px-3',
            isItemActive(item)
              ? 'bg-white dark:bg-[#171717] text-blue-600 dark:text-blue-400 font-bold shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white',
          ]"
          :title="isSidebarCollapsed ? item.name : ''"
        >
          <LucideIcon
            :name="item.icon"
            class="h-5 w-5 shrink-0"
            :class="
              isItemActive(item)
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300'
            "
            :stroke-width="2"
          />
          <span v-if="!isSidebarCollapsed" class="ml-3 truncate font-medium">{{
            item.name
          }}</span>
        </NuxtLink>

        <!-- History Section -->
        <div class="mt-8 mb-2">
          <div
            v-if="!isSidebarCollapsed"
            class="px-3 text-xs font-semibold text-slate-400 dark:text-slate-500 whitespace-nowrap"
          >
            历史对话
          </div>
          <div
            v-else
            class="h-[1px] bg-slate-200 dark:bg-white/10 mx-2 my-4"
          ></div>

          <div v-if="loadingHistory" class="mt-2 px-3 text-xs text-slate-400">
            加载中...
          </div>

          <div
            v-else-if="!filteredHistoryProjects.length && !isSidebarCollapsed"
            class="mt-2 px-3 text-xs text-slate-400"
          >
            暂无历史记录
          </div>

          <div class="space-y-1 mt-2" v-else>
            <div
              v-for="project in filteredHistoryProjects"
              :key="project.id"
              class="group relative"
            >
              <button
                @click="openHistoryProject(project.id)"
                class="w-full group flex items-center py-2 text-sm font-medium rounded-xl transition-all"
                :class="[
                  isSidebarCollapsed ? 'justify-center px-0' : 'px-3 pr-[40px]',
                  activeHistoryProjectId === project.id
                    ? 'bg-white dark:bg-[#171717] text-slate-900 dark:text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-white',
                ]"
                :title="isSidebarCollapsed ? project.title : ''"
              >
                <LucideIcon
                  name="MessageSquare"
                  class="h-4 w-4 shrink-0"
                  :class="
                    activeHistoryProjectId === project.id
                      ? 'text-slate-900 dark:text-white'
                      : 'text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300'
                  "
                  :stroke-width="2"
                />
                <span
                  v-if="!isSidebarCollapsed"
                  class="ml-3 truncate font-medium"
                >
                  {{ project.title || "新对话" }}
                </span>
              </button>

              <div
                v-if="!isSidebarCollapsed"
                class="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 pointer-events-none transition-opacity group-hover:opacity-100 group-hover:pointer-events-auto"
                :class="
                  activeHistoryProjectId === project.id
                    ? 'opacity-100 pointer-events-auto'
                    : ''
                "
              >
                <DropdownMenu>
                  <DropdownMenuTrigger as-child>
                    <button
                      @click.stop
                      class="flex items-center justify-center w-6 h-6 rounded-md bg-[#f3f4f6] dark:bg-white/8 text-[#6b7280] hover:text-[#1f2937] hover:bg-[#ebedef] dark:hover:bg-white/12 transition-colors"
                      title="更多操作"
                    >
                      <LucideIcon
                        name="Ellipsis"
                        class="w-3 h-3"
                        :stroke-width="1.8"
                      />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    side="bottom"
                    :side-offset="10"
                    class="w-[128px] translate-x-28 rounded-[16px] border border-[#ececec] bg-[#ffffff] p-2 shadow-[0_20px_48px_rgba(15,23,42,0.16)]"
                  >
                    <DropdownMenuItem
                      class="rounded-md px-2 py-2 text-[13px] font-medium text-[#1f2937] hover:bg-[#f8fafc] focus:bg-[#f8fafc]"
                      @select="startRenameProject(project)"
                    >
                      <LucideIcon
                        name="SquarePen"
                        class="w-5 h-5"
                        :stroke-width="1.7"
                      />
                      <span>编辑</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      class="rounded-md px-2 py-2 text-[13px] font-medium text-[#ef4444] hover:bg-[#fef2f2] focus:bg-[#fef2f2] focus:text-[#ef4444]"
                      @select="deleteProject(project)"
                    >
                      <LucideIcon
                        v-if="deletingProjectId !== project.id"
                        name="Trash2"
                        class="w-5 h-5"
                        :stroke-width="1.7"
                      />
                      <LucideIcon
                        v-else
                        name="Loader2"
                        class="w-5 h-5 animate-spin"
                      />
                      <span>删除</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <!-- User Menu Section -->
      <div
        id="user-menu-container"
        class="relative mt-auto border-t border-slate-200 dark:border-white/5"
        :class="isSidebarCollapsed ? 'p-2' : 'px-4 py-4'"
      >
        <!-- Popover -->
        <div
          v-if="isUserMenuOpen"
          class="absolute bottom-2 left-full ml-3 w-60 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] shadow-[0_4px_24px_rgba(0,0,0,0.1)] dark:shadow-[0_4px_24px_rgba(0,0,0,0.5)] z-[100] transform-gpu origin-bottom-left scale-100 transition-all"
        >
          <!-- Header -->
          <div
            class="px-3 py-3 flex items-center gap-3 border-b border-slate-100 dark:border-white/5"
            @mouseenter="activeSubmenu = null"
          >
            <img
              src="~/assets/image/icon.webp"
              class="w-9 h-9 rounded-full bg-slate-100 dark:bg-black/20 shrink-0 object-cover border border-slate-200 dark:border-white/10"
            />
            <div class="flex-1 min-w-0">
              <div
                class="text-[13px] font-medium text-slate-900 dark:text-white truncate"
              >
                {{ auth.user.value?.display_name || "招招营大总管" }}
              </div>
              <div class="text-xs text-slate-500 dark:text-slate-400 truncate">
                {{ auth.user.value?.email || "admin@admin.com" }}
              </div>
            </div>
          </div>

          <!-- Section 2 -->
          <div
            class="border-t border-slate-100 dark:border-white/5 py-1"
            @mouseenter="activeSubmenu = null"
          >
            <button
              @click="goToSystemSettings"
              class="w-full px-4 py-2 text-left text-[13px] text-slate-700 dark:text-slate-200 flex items-center gap-3 hover:bg-slate-50 dark:hover:bg-white/5 transition"
            >
              <LucideIcon
                name="UserRound"
                class="w-4 h-4 text-slate-500"
                :stroke-width="2"
              />
              系统设置
            </button>
          </div>

          <!-- Section 3 settings -->
          <div class="border-t border-slate-100 dark:border-white/5 py-1">
            <!-- Theme Submenu Wrapper -->
            <div class="relative" @mouseenter="activeSubmenu = 'theme'">
              <button
                @click.stop="
                  activeSubmenu = activeSubmenu === 'theme' ? null : 'theme'
                "
                class="w-full px-4 py-2 text-left text-[13px] text-slate-700 dark:text-slate-200 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-white/5 transition"
                :class="{
                  'bg-slate-50 dark:bg-white/5': activeSubmenu === 'theme',
                }"
              >
                <div class="flex items-center gap-3">
                  <LucideIcon
                    v-if="themePref === 'light'"
                    name="Sun"
                    class="w-4 h-4 text-slate-500"
                    :stroke-width="2"
                  />
                  <LucideIcon
                    v-else-if="themePref === 'dark'"
                    name="Moon"
                    class="w-4 h-4 text-slate-500"
                    :stroke-width="2"
                  />
                  <LucideIcon
                    v-else
                    name="Monitor"
                    class="w-4 h-4 text-slate-500"
                    :stroke-width="2"
                  />
                  主题
                </div>
                <LucideIcon
                  name="ChevronRight"
                  class="w-4 h-4 text-slate-400"
                  :stroke-width="2"
                />
              </button>

              <div
                v-if="activeSubmenu === 'theme'"
                class="absolute left-full top-0 ml-1 w-32 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] shadow-xl z-[110] py-1 overflow-hidden transform-gpu origin-top-left transition-all"
              >
                <button
                  @click="setTheme('light')"
                  class="w-full px-4 py-2 text-left text-[13px] text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition flex items-center justify-between whitespace-nowrap"
                >
                  <div class="flex items-center gap-2">
                    <LucideIcon
                      name="Sun"
                      class="w-4 h-4 text-slate-500"
                      :stroke-width="2"
                    />
                    浅色
                  </div>
                  <LucideIcon
                    v-if="themePref === 'light'"
                    name="Check"
                    class="w-4 h-4 text-slate-900 dark:text-white"
                    :stroke-width="2"
                  />
                </button>
                <button
                  @click="setTheme('dark')"
                  class="w-full px-4 py-2 text-left text-[13px] text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition flex items-center justify-between whitespace-nowrap"
                >
                  <div class="flex items-center gap-2">
                    <LucideIcon
                      name="Moon"
                      class="w-4 h-4 text-slate-500"
                      :stroke-width="2"
                    />
                    深色
                  </div>
                  <LucideIcon
                    v-if="themePref === 'dark'"
                    name="Check"
                    class="w-4 h-4 text-slate-900 dark:text-white"
                    :stroke-width="2"
                  />
                </button>
                <button
                  @click="setTheme('system')"
                  class="w-full px-4 py-2 text-left text-[13px] text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition flex items-center justify-between whitespace-nowrap"
                >
                  <div class="flex items-center gap-2">
                    <LucideIcon
                      name="Monitor"
                      class="w-4 h-4 text-slate-500"
                      :stroke-width="2"
                    />
                    系统跟从
                  </div>
                  <LucideIcon
                    v-if="themePref === 'system'"
                    name="Check"
                    class="w-4 h-4 text-slate-900 dark:text-white"
                    :stroke-width="2"
                  />
                </button>
              </div>
            </div>
          </div>

          <!-- Section 4 Logout -->
          <div
            class="border-t border-slate-100 dark:border-white/5 p-2"
            @mouseenter="activeSubmenu = null"
          >
            <button
              @click="handleLogout"
              :disabled="logoutLoading"
              class="w-full px-3 py-2 text-left text-[13px] font-medium text-slate-700 dark:text-slate-200 flex items-center gap-3 rounded-lg bg-slate-50 hover:bg-slate-100 dark:bg-white/5 dark:hover:bg-white/10 transition"
            >
              <LucideIcon
                name="LogOut"
                class="w-4 h-4 text-rose-500"
                :stroke-width="2"
              />
              <span class="text-rose-500">退出登录</span>
            </button>
          </div>
        </div>

        <!-- Popover Trigger Button -->
        <button
          @click="toggleUserMenu"
          class="flex items-center w-full rounded-xl hover:bg-black/5 dark:hover:bg-white/5 transition-all group overflow-hidden"
          :class="isSidebarCollapsed ? 'p-1.5 justify-center' : 'px-3 py-2'"
        >
          <img
            src="~/assets/image/icon.webp"
            class="w-8 h-8 rounded-full bg-slate-200 dark:bg-black/20 shrink-0 object-cover border border-slate-300/50 dark:border-white/10"
          />
          <div
            v-if="!isSidebarCollapsed"
            class="ml-3 flex-1 overflow-hidden text-left"
          >
            <p
              class="truncate text-[13px] font-medium text-slate-900 dark:text-white"
            >
              {{ auth.user.value?.display_name || "招招营大总管" }}
            </p>
            <p class="truncate text-xs text-slate-500 dark:text-slate-400">
              {{ (auth.user.value?.email || "admin@admin.com").split("@")[0] }}
            </p>
          </div>
          <div
            v-if="!isSidebarCollapsed"
            class="ml-2 shrink-0 h-5 w-5 flex items-center justify-center text-slate-400 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300"
          >
            <LucideIcon
              name="ChevronsUpDown"
              class="h-4 w-4"
              :stroke-width="2"
            />
          </div>
        </button>
      </div>
    </aside>

    <!-- Main Content wrapper -->
    <div
      class="flex-1 flex flex-col min-w-0 bg-[#ffffff] dark:bg-[#171717] overflow-hidden"
    >
      <!-- Top header with toggle button -->
      <header
        class="flex h-14 w-full shrink-0 items-center justify-between border-b border-slate-200 dark:border-white/10 px-4 transition-colors"
      >
        <div class="flex items-center gap-4">
          <!-- Collapse Toggle button -->
          <button
            @click="toggleSidebar"
            class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/10 transition-colors"
          >
            <LucideIcon name="PanelLeft" class="h-5 w-5" :stroke-width="2" />
          </button>

          <div class="h-4 w-px bg-slate-200 dark:bg-white/10"></div>

          <!-- Page Title / Breadcrumb -->
          <span class="text-sm font-medium text-slate-900 dark:text-white">{{
            currentRouteName
          }}</span>
        </div>

        <div class="flex items-center gap-3">
          <!-- Optional Top Header Items, e.g. Notifications -->
          <button
            class="relative flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/10 transition-colors"
          >
            <LucideIcon name="Bell" class="h-5 w-5" :stroke-width="2" />
            <span
              class="absolute right-1 top-1.5 flex h-2 w-2 rounded-full bg-rose-500"
            ></span>
          </button>
        </div>
      </header>

      <!-- Actual Content -->
      <main class="flex-1 overflow-x-hidden overflow-y-auto w-full relative">
        <NuxtPage />
      </main>
    </div>
  </div>

  <InputPromptModal
    :open="renamingProjectId !== null"
    title="编辑历史对话"
    :value="renameDraft"
    :error="renameModalError"
    :pending="renamingProjectPending"
    placeholder="请输入新的标题"
    confirm-text="保存"
    @close="cancelRenameProject"
    @confirm="submitRenameProject"
    @update:value="renameDraft = $event"
  />

  <ConfirmModal
    :model-value="projectToDelete !== null"
    @update:modelValue="
      (value) => {
        if (!value) {
          cancelDeleteProject();
        }
      }
    "
    title="删除历史对话"
    :message="`删除后不可恢复。${projectToDelete?.title ? `\n\n${projectToDelete.title}` : ''}`"
    confirm-text="删除"
    cancel-text="取消"
    :loading="
      Boolean(projectToDelete && deletingProjectId === projectToDelete.id)
    "
    @confirm="confirmDeleteProject"
    @cancel="cancelDeleteProject"
  />

  <Toaster position="top-right" :duration="3000" rich-colors close-button />
</template>
