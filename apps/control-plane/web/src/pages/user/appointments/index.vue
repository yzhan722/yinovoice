<template>
  <div class="demo-page appointments-page">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">预约结果</h1>
        <p class="demo-page-sub">规划中 · 演示框架；尚未接通实时语音或电话流程。</p>
      </div>
    </div>

    <div class="month demo-card">
      <div class="month-head">
        <strong>{{ monthLabel }}</strong>
        <span>{{ list.length }} upcoming</span>
      </div>
      <div class="cal-grid">
        <span v-for="w in weekdays" :key="w" class="wd">{{ w }}</span>
        <button
          v-for="cell in calendarCells"
          :key="cell.key"
          type="button"
          class="day"
          :class="{ mute: !cell.inMonth, active: cell.hasEvent }"
        >
          {{ cell.day }}
        </button>
      </div>
    </div>

    <h2 class="section">Upcoming</h2>
    <div class="cards">
      <article v-for="row in list" :key="row.id" class="demo-list-card">
        <div>
          <div class="top">
            <span class="demo-prio" :class="row.status === 'pending' ? 'high' : row.status === 'confirmed' ? 'low' : 'medium'">
              {{ statusLabel(row.status) }}
            </span>
          </div>
          <h3>{{ row.patientName }} · {{ row.service }}</h3>
          <p>{{ formatRange(row.slotStart, row.slotEnd) }}</p>
          <div class="meta">{{ row.phone }}</div>
        </div>
      </article>
      <div v-if="!loading && !list.length" class="empty">暂无预约</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import { TenantAppointmentService } from '@/api/platform';

const svc = new TenantAppointmentService();
const loading = ref(false);
const list = ref<any[]>([]);
const weekdays = ['一', '二', '三', '四', '五', '六', '日'];

const monthLabel = computed(() => {
  const d = new Date();
  return `${d.getFullYear()}年${d.getMonth() + 1}月`;
});

const eventDays = computed(() => {
  const set = new Set<number>();
  list.value.forEach((row) => {
    try {
      set.add(new Date(row.slotStart).getDate());
    } catch (_) {}
  });
  return set;
});

const calendarCells = computed(() => {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  const first = new Date(y, m, 1);
  const startPad = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const cells: { key: string; day: number; inMonth: boolean; hasEvent: boolean }[] = [];
  for (let i = 0; i < startPad; i += 1) {
    cells.push({ key: `p-${i}`, day: 0, inMonth: false, hasEvent: false });
  }
  for (let d = 1; d <= daysInMonth; d += 1) {
    cells.push({
      key: `d-${d}`,
      day: d,
      inMonth: true,
      hasEvent: eventDays.value.has(d),
    });
  }
  return cells;
});

function statusLabel(s: string) {
  return ({ confirmed: '已确认', cancelled: '已取消', pending: '待确认' } as any)[s] || s;
}

function formatRange(start: string, end: string) {
  try {
    const a = new Date(start);
    const b = new Date(end);
    return `${a.toLocaleString()} ~ ${b.toLocaleTimeString()}`;
  } catch (_) {
    return `${start} ~ ${end}`;
  }
}

async function load() {
  loading.value = true;
  try {
    const res: any = await svc.list();
    list.value = res?.list ?? [];
  } catch (e: any) {
    MessagePlugin.error(e?.message || '加载失败');
    list.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="less">
.page-head { margin-bottom: 14px; }

.month {
  padding: 16px;
  margin-bottom: 16px;
}

.month-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  strong { font-size: 16px; }
  span { font-size: 12px; color: var(--demo-muted); font-weight: 700; }
}

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.wd {
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--demo-muted);
  padding: 4px 0;
}

.day {
  aspect-ratio: 1;
  border: 0;
  border-radius: 12px;
  background: #f8f8fc;
  font-size: 12px;
  font-weight: 700;
  font-family: inherit;
  color: var(--demo-ink);
  &.mute { visibility: hidden; }
  &.active {
    background: var(--demo-primary-soft);
    color: var(--demo-primary);
    box-shadow: inset 0 0 0 1px #c7c9ff;
  }
}

.section {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 800;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

h3 {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 800;
}

p, .meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--demo-muted);
}

.empty {
  padding: 24px;
  text-align: center;
  color: var(--demo-muted);
}
</style>
