<script setup lang="ts">
import Card from "@/components/ui/card/Card.vue";
import CardContent from "@/components/ui/card/CardContent.vue";
import CardHeader from "@/components/ui/card/CardHeader.vue";
import CardTitle from "@/components/ui/card/CardTitle.vue";

const { t } = useI18n();

definePageMeta({
  layout: "console",
  middleware: "auth",
});

useHead({
  title: computed(() => t("dashboard.pageTitle")),
});

const stats = computed(() => [
  {
    name: t("dashboard.totalSessions"),
    value: "2,834",
    change: "+12%",
    trend: "up",
  },
  {
    name: t("dashboard.successRate"),
    value: "98.5%",
    change: "+0.4%",
    trend: "up",
  },
  {
    name: t("dashboard.activeUsers"),
    value: "142",
    change: "-2%",
    trend: "down",
  },
  { name: t("dashboard.apiCalls"), value: "1.2M", change: "+24%", trend: "up" },
]);
</script>

<template>
  <div class="px-6 py-8 md:px-8">
    <div class="mx-auto max-w-6xl space-y-8">
      <div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Card
          v-for="stat in stats"
          :key="stat.name"
          class="border-[#e2e8f0]/60 dark:border-white/10 bg-white/80 dark:bg-white/5 shadow-sm backdrop-blur transition-colors"
        >
          <CardHeader class="pb-2">
            <CardTitle
              class="text-sm font-medium text-slate-500 dark:text-slate-400"
              >{{ stat.name }}</CardTitle
            >
          </CardHeader>
          <CardContent>
            <div class="text-3xl font-bold text-slate-900 dark:text-white">
              {{ stat.value }}
            </div>
            <p
              class="mt-1 flex items-center text-xs"
              :class="stat.trend === 'up' ? 'text-green-600' : 'text-red-500'"
            >
              <LucideIcon
                v-if="stat.trend === 'up'"
                name="TrendingUp"
                class="mr-1 h-3 w-3"
                :stroke-width="2"
              />
              <LucideIcon
                v-else
                name="TrendingDown"
                class="mr-1 h-3 w-3"
                :stroke-width="2"
              />
              {{ stat.change }}
              <span class="ml-1 text-slate-500">{{
                $t("dashboard.vsLastWeek")
              }}</span>
            </p>
          </CardContent>
        </Card>
      </div>

      <Card
        class="border-[#e2e8f0]/60 dark:border-white/10 bg-white/80 dark:bg-white/5 shadow-sm backdrop-blur transition-colors"
      >
        <CardHeader>
          <CardTitle class="dark:text-white">{{
            $t("dashboard.systemTrend")
          }}</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            class="flex h-72 items-center justify-center rounded-xl border border-dashed border-[#e2e8f0] dark:border-white/10 bg-slate-50/50 dark:bg-black/20"
          >
            <div class="text-center">
              <LucideIcon
                name="ChartColumn"
                class="mx-auto h-12 w-12 text-slate-300 dark:text-slate-600"
                :stroke-width="1.5"
              />
              <p class="mt-4 text-sm font-medium text-slate-500">
                {{ $t("dashboard.chartLoading") }}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
