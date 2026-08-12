<template>
  <div class="admin-demo-stub">
    <t-card title="运营端（第一阶段未演示）" :bordered="false">
      <t-alert
        theme="warning"
        message="当前 Demo 只讲租户端。运营模板/租户管理菜单已隐藏；模板页仍可通过直链访问供内部调试。"
        style="margin-bottom: 16px"
      />
      <p>租户演示账号：登录页使用 <code>demo</code> / <code>demo123</code>（Hash 路由 <code>#/login</code>）。</p>
      <t-space style="margin-top: 16px">
        <t-button theme="primary" variant="outline" @click="goTemplates">打开模板页（调试）</t-button>
      </t-space>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();
function goTemplates() {
  router.push('/admin/templates');
}
</script>

<style scoped lang="less">
.admin-demo-stub {
  padding: 24px;
  max-width: 640px;

  p {
    color: var(--td-text-color-secondary);
    line-height: 1.6;
  }

  code {
    padding: 0 4px;
    background: var(--td-bg-color-secondarycontainer);
    border-radius: 3px;
  }
}
</style>
