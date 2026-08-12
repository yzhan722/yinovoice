<template>
  <nav v-if="visible" class="bottom-nav" aria-label="主导航">
    <button
      v-for="item in items"
      :key="item.path"
      type="button"
      class="nav-item"
      :class="{ active: isActive(item.path) }"
      @click="go(item.path)"
    >
      <t-icon :name="item.icon" class="nav-icon" />
      <span>{{ item.label }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const isMobile = ref(false);

const items = [
  { path: '/user/dashboard', label: '工作台', icon: 'dashboard' },
  { path: '/user/callback-tasks', label: '回拨', icon: 'task' },
  { path: '/user/appointments', label: '预约', icon: 'calendar' },
  { path: '/user/call-history', label: '通话', icon: 'call' },
  { path: '/user/profile', label: '我的', icon: 'user' },
];

const visible = computed(() => isMobile.value && route.path.startsWith('/user'));

function sync() {
  isMobile.value = window.innerWidth <= 768;
}

function isActive(path: string) {
  if (path === '/user/profile') {
    return ['/user/profile', '/user/achievements', '/user/celebration', '/user/assistant-settings'].some(
      (p) => route.path === p || route.path.startsWith(`${p}/`),
    );
  }
  return route.path === path || route.path.startsWith(`${path}/`);
}

function go(path: string) {
  router.push(path);
}

onMounted(() => {
  sync();
  window.addEventListener('resize', sync);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', sync);
});
</script>

<style scoped lang="less">
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 300;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  height: calc(var(--demo-bottom-nav-h) + env(safe-area-inset-bottom, 0px));
  padding: 6px 4px calc(6px + env(safe-area-inset-bottom, 0px));
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid var(--demo-line);
  backdrop-filter: blur(10px);
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: 0;
  background: transparent;
  color: var(--demo-muted);
  font-size: 11px;
  font-weight: 600;
  font-family: var(--demo-font);
  cursor: pointer;

  &.active {
    color: var(--demo-primary);
  }
}

.nav-icon {
  font-size: 20px;
}
</style>
