<script setup lang="ts">
import { navigateTo } from 'nuxt/app';

definePageMeta({
  middleware: [
    function (to, from) {
      return navigateTo('/new-chat');
    }
  ]
});
</script>
<template>
  <div class="flex items-center justify-center h-full w-full">
    Redirecting...
  </div>
</template>
