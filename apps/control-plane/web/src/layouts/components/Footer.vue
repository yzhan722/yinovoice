<template>
  <div :class="prefix + '-footer'">YinoVapi Demo · 路径 A（通话接入位已预留）</div>
</template>

<script setup lang="ts">
import { prefix } from '@/config/global';

const year = new Date().getFullYear();
</script>

<style lang="less" scoped>
.@{starter-prefix}-footer {
  color: var(--td-text-color-placeholder);
  line-height: 20px;
  text-align: center;
}
</style>
