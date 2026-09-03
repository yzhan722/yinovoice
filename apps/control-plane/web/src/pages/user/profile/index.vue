<template>
  <div class="demo-page profile">
    <div class="hero demo-card">
      <div class="avatar">太</div>
      <div>
        <h1 class="name">{{ name }}</h1>
        <p class="email">常州太平洋口腔 · 新北旗舰店</p>
        <p class="meta">demo@pacific-dental · 前台语音实例</p>
      </div>
    </div>

    <div class="menu demo-card">
      <button v-for="item in menus" :key="item.label" type="button" class="row" @click="go(item.path)">
        <span class="left">
          <span class="ico" :style="{ background: item.bg, color: item.fg }"><t-icon :name="item.icon" /></span>
          {{ item.label }}
        </span>
        <t-icon name="chevron-right" />
      </button>
    </div>

    <button type="button" class="logout" @click="logout">退出登录</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/store';

const router = useRouter();
const user = useUserStore();
const name = computed(() => user.userInfo?.name || user.userInfo?.nickname || '太平洋口腔');

const menus = [
  { label: '我的实例', path: '/user/assistant-settings', icon: 'setting', bg: '#EEF0FF', fg: '#5B4DFF' },
  { label: '学习计划', path: '/user/planner', icon: 'calendar', bg: '#E0F2FE', fg: '#0284C7' },
  { label: '知识库', path: '/user/knowledge-base', icon: 'file', bg: '#DCFCE7', fg: '#16A34A' },
];

function go(path: string) {
  router.push(path);
}

async function logout() {
  await user.logout();
  router.push('/login');
}
</script>

<style scoped lang="less">
.hero {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 20px;
  margin-bottom: 14px;
}

.avatar {
  width: 72px;
  height: 72px;
  border-radius: 24px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #5b4dff, #7c3aed);
  color: #fff;
  font-size: 28px;
  font-weight: 800;
}

.name {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
}

.email,
.meta {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--demo-muted);
}

.menu {
  padding: 6px 8px;
  overflow: hidden;
}

.row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 10px;
  border: 0;
  border-bottom: 1px solid var(--demo-line);
  background: transparent;
  font-family: inherit;
  font-size: 14px;
  font-weight: 700;
  color: var(--demo-ink);
  cursor: pointer;

  &:last-child {
    border-bottom: 0;
  }
}

.left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ico {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: grid;
  place-items: center;
}

.logout {
  margin-top: 18px;
  width: 100%;
  border: 1px solid #fecaca;
  background: #fff;
  color: #dc2626;
  border-radius: 999px;
  padding: 12px;
  font-weight: 800;
  font-family: inherit;
  cursor: pointer;
}
</style>
