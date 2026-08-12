<template>
  <t-config-provider :global-config="getComponentsLocale">
    <router-view :key="locale" :class="[mode]"
  /></t-config-provider>
</template>
<script setup lang="ts">
import { computed, onMounted } from 'vue';

import { useLocale } from '@/locales/useLocale';
import { useSettingStore } from '@/store';

const store = useSettingStore();
const TARGET_BRAND = '#5B4DFF';

onMounted(() => {
  if (store.brandTheme !== TARGET_BRAND) {
    store.updateConfig({ brandTheme: TARGET_BRAND });
  }
});

const mode = computed(() => {
  return store.displayMode;
});
const { getComponentsLocale, locale } = useLocale();
</script>
<style lang="less" scoped>
#nprogress .bar {
  background: var(--td-brand-color) !important;
}
</style>
