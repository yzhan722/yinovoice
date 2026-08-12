<template>
  <div class="celebration">
    <div class="burst" aria-hidden="true" />
    <div class="trophy">🏆</div>
    <h1>Great Work!</h1>
    <p class="name">{{ name }}</p>
    <p class="desc">本周跟进与回拨目标已达成，继续保持连续打卡。</p>
    <div class="actions">
      <button type="button" class="primary" @click="$router.push('/user/achievements')">查看成就</button>
      <button type="button" class="ghost" @click="$router.push('/user/dashboard')">返回工作台</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useUserStore } from '@/store';

const user = useUserStore();
const name = computed(() => user.userInfo?.name || user.userInfo?.nickname || '太平洋口腔');
</script>

<style scoped lang="less">
.celebration {
  min-height: calc(100vh - 120px);
  margin: -8px -4px;
  padding: 64px 24px 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #fff;
  background: radial-gradient(circle at 50% 20%, #7c3aed 0%, #4c1d95 45%, #2e1065 100%);
  border-radius: 0;
  position: relative;
  overflow: hidden;
  font-family: var(--demo-font);
}

.burst {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 20% 30%, rgba(255, 215, 0, 0.35) 0 2px, transparent 3px),
    radial-gradient(circle at 80% 25%, rgba(255, 255, 255, 0.35) 0 2px, transparent 3px),
    radial-gradient(circle at 30% 70%, rgba(251, 191, 36, 0.4) 0 2px, transparent 3px),
    radial-gradient(circle at 70% 75%, rgba(255, 255, 255, 0.3) 0 2px, transparent 3px);
  pointer-events: none;
}

.trophy {
  font-size: 72px;
  filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.25));
  animation: pop 0.6s ease;
}

h1 {
  margin: 18px 0 0;
  font-size: 36px;
  font-weight: 800;
}

.name {
  margin: 8px 0 0;
  font-size: 18px;
  font-weight: 700;
  opacity: 0.95;
}

.desc {
  margin: 12px 0 0;
  max-width: 320px;
  font-size: 14px;
  line-height: 1.5;
  opacity: 0.85;
}

.actions {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(280px, 100%);
}

.primary,
.ghost {
  border-radius: 999px;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  font-family: inherit;
}

.primary {
  border: 0;
  background: #fbbf24;
  color: #3b0764;
}

.ghost {
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: transparent;
  color: #fff;
}

@keyframes pop {
  from {
    transform: scale(0.6);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

@media (min-width: 769px) {
  .celebration {
    min-height: 640px;
    border-radius: 24px;
    margin: 8px auto;
    max-width: 720px;
  }
}
</style>
