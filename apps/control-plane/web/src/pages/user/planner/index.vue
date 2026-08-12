<template>
  <div class="demo-page planner">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">学习计划</h1>
        <p class="demo-page-sub">Study Planner · 跟进与预约时间线</p>
      </div>
    </div>

    <div class="dates">
      <button
        v-for="d in dates"
        :key="d.key"
        type="button"
        class="date-chip"
        :class="{ active: d.key === activeDate }"
        @click="activeDate = d.key"
      >
        <span class="dow">{{ d.dow }}</span>
        <strong>{{ d.day }}</strong>
      </button>
    </div>

    <ul class="timeline">
      <li v-for="item in timeline" :key="item.id" class="demo-list-card">
        <div class="left">
          <div class="time">{{ item.time }}</div>
          <div class="dot" :class="item.tone" />
        </div>
        <div class="content">
          <div class="title">{{ item.title }}</div>
          <div class="sub">{{ item.sub }}</div>
          <span class="demo-prio" :class="item.prio">{{ item.prioLabel }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const now = new Date();
const dates = Array.from({ length: 7 }).map((_, i) => {
  const d = new Date(now);
  d.setDate(now.getDate() - 1 + i);
  const key = d.toISOString().slice(0, 10);
  const dow = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()];
  return { key, dow, day: String(d.getDate()).padStart(2, '0') };
});

const activeDate = ref(dates[1]?.key || dates[0].key);

const timeline = computed(() => [
  {
    id: 1,
    time: '09:00',
    title: '回拨 · 种植咨询未接通',
    sub: '来电 138****6521',
    tone: 'warn',
    prio: 'high',
    prioLabel: 'High',
  },
  {
    id: 2,
    time: '11:30',
    title: '预约确认 · 洗牙护理',
    sub: '新北旗舰店 · 李医生',
    tone: 'ok',
    prio: 'medium',
    prioLabel: 'Medium',
  },
  {
    id: 3,
    time: '14:00',
    title: '跟进 · 正畸方案说明',
    sub: '待处理事项',
    tone: 'primary',
    prio: 'low',
    prioLabel: 'Low',
  },
  {
    id: 4,
    time: '16:30',
    title: '实例巡检 · 新北前台',
    sub: '知识库与话术抽检',
    tone: 'primary',
    prio: 'medium',
    prioLabel: 'Medium',
  },
]);
</script>

<style scoped lang="less">
.page-head {
  margin-bottom: 14px;
}

.dates {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 8px;
  margin-bottom: 14px;
}

.date-chip {
  flex: 0 0 auto;
  width: 56px;
  padding: 10px 0;
  border: 1px solid var(--demo-line);
  border-radius: 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-family: inherit;

  .dow {
    font-size: 11px;
    color: var(--demo-muted);
    font-weight: 600;
  }

  strong {
    font-size: 16px;
  }

  &.active {
    background: var(--demo-primary);
    border-color: var(--demo-primary);
    color: #fff;
    .dow {
      color: rgba(255, 255, 255, 0.8);
    }
  }
}

.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.demo-list-card {
  align-items: stretch;
}

.left {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 52px;
}

.time {
  font-size: 12px;
  font-weight: 800;
  color: var(--demo-muted);
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  &.warn { background: #f59e0b; }
  &.ok { background: #22c55e; }
  &.primary { background: #5b4dff; }
}

.content {
  flex: 1;
}

.title {
  font-size: 14px;
  font-weight: 800;
}

.sub {
  margin: 4px 0 8px;
  font-size: 12px;
  color: var(--demo-muted);
}
</style>
