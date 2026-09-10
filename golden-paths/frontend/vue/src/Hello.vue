<script setup lang="ts">
// Golden path — Frontend / Vue3 (B160). The demo component the page renders and the lane tests.
withDefaults(defineProps<{ name?: string }>(), { name: 'weyland' });
</script>

<template>
  <h1>hello, {{ name }}</h1>
</template>
