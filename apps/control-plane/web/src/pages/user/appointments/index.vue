<template>
  <div class="demo-page appointments-page">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">预约结果</h1>
        <p class="demo-page-sub">租户真实预约队列 · 本阶段不发起外呼</p>
      </div>
      <button type="button" class="primary" data-testid="new-appointment" @click="showForm = !showForm">
        {{ showForm ? '收起' : '新建预约' }}
      </button>
    </div>

    <form v-if="showForm" class="create-form demo-card" @submit.prevent="createAppointment">
      <label>姓名<input v-model="form.patientName" required data-testid="apt-name" /></label>
      <label>电话<input v-model="form.phone" required data-testid="apt-phone" /></label>
      <label>项目<input v-model="form.service" required data-testid="apt-service" /></label>
      <label>开始<input v-model="form.slotStart" type="datetime-local" required data-testid="apt-start" /></label>
      <label>结束<input v-model="form.slotEnd" type="datetime-local" required data-testid="apt-end" /></label>
      <button type="submit" class="primary" :disabled="saving" data-testid="apt-submit">
        {{ saving ? '保存中…' : '创建' }}
      </button>
      <p v-if="formError" class="error" role="alert">{{ formError }}</p>
    </form>

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
      <article v-for="row in list" :key="row.id" class="demo-list-card" data-testid="appointment-row">
        <div>
          <div class="top">
            <span class="demo-prio" :class="row.status === 'pending' ? 'high' : row.status === 'confirmed' ? 'low' : 'medium'">
              {{ statusLabel(row.status) }}
            </span>
            <span v-if="row.source === 'voice_tool'" class="source-tag" data-testid="voice-auto-tag">语音自动</span>
          </div>
          <h3>{{ row.patientName }} · {{ row.service }}</h3>
          <p>{{ formatRange(row.slotStart, row.slotEnd) }}</p>
          <div class="meta">{{ row.phone }}</div>
          <p v-if="row.notes" class="notes" data-testid="appointment-notes">{{ row.notes }}</p>
          <RouterLink
            v-if="row.callRecordId"
            class="call-link"
            data-testid="appointment-call-link"
            :to="`/user/call-history/detail/${row.callRecordId}`"
          >
            查看通话
          </RouterLink>
        </div>
        <div class="row-actions">
          <button
            v-if="row.status === 'pending'"
            type="button"
            data-testid="confirm-appointment"
            @click="setStatus(row, 'confirmed')"
          >
            确认
          </button>
          <button
            v-if="row.status !== 'cancelled'"
            type="button"
            data-testid="cancel-appointment"
            @click="cancelAppointment(row)"
          >
            取消
          </button>
        </div>
      </article>
      <div v-if="loading" class="empty">加载中…</div>
      <div v-else-if="!list.length" class="empty">暂无预约</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { TenantAppointmentService } from '@/api/platform';

const svc = new TenantAppointmentService();
const loading = ref(false);
const saving = ref(false);
const showForm = ref(false);
const formError = ref('');
const list = ref<any[]>([]);
const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
const form = ref({
  patientName: '',
  phone: '',
  service: '',
  slotStart: '',
  slotEnd: '',
});

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

function toIsoLocal(value: string) {
  const date = new Date(value);
  return date.toISOString();
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

async function createAppointment() {
  saving.value = true;
  formError.value = '';
  try {
    const slotStart = toIsoLocal(form.value.slotStart);
    const slotEnd = toIsoLocal(form.value.slotEnd);
    if (new Date(slotEnd).getTime() < new Date(slotStart).getTime()) {
      formError.value = '日期不可使用：结束时间不能早于开始时间';
      return;
    }
    if (Number.isNaN(new Date(slotStart).getTime()) || Number.isNaN(new Date(slotEnd).getTime())) {
      formError.value = '日期不可使用：请选择有效的开始与结束时间';
      return;
    }
    await svc.create({
      patientName: form.value.patientName,
      phone: form.value.phone,
      service: form.value.service,
      slotStart,
      slotEnd,
    });
    showForm.value = false;
    form.value = { patientName: '', phone: '', service: '', slotStart: '', slotEnd: '' };
    await load();
  } catch (e: any) {
    const msg = String(e?.message || '');
    if (msg.includes('slot_end') || msg.includes('422') || msg.includes('日期')) {
      formError.value = '日期不可使用';
    } else {
      formError.value = msg || '创建失败';
    }
  } finally {
    saving.value = false;
  }
}

async function setStatus(row: any, status: string) {
  try {
    await svc.update(row.id, { status });
    await load();
  } catch (e: any) {
    MessagePlugin.error(e?.message || '更新失败');
  }
}

async function cancelAppointment(row: any) {
  if (!window.confirm('确认取消该预约？')) return;
  try {
    await svc.cancel(row.id);
    await load();
  } catch (e: any) {
    MessagePlugin.error(e?.message || '取消失败');
  }
}

onMounted(load);
</script>

<style scoped lang="less">
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.primary {
  border: 0;
  border-radius: 7px;
  padding: 9px 14px;
  background: var(--demo-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.create-form {
  display: grid;
  gap: 10px;
  padding: 14px;
  margin-bottom: 14px;
  label {
    display: grid;
    gap: 4px;
    font-size: 12px;
    color: var(--demo-muted);
  }
  input {
    padding: 8px 10px;
    border: 1px solid var(--demo-line);
    border-radius: 6px;
  }
}

.error { color: #c62828; margin: 0; font-size: 13px; }

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

.demo-list-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.source-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: #0b5fff;
  background: #e8f0ff;
}

.notes {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--demo-ink);
  white-space: pre-wrap;
}

.call-link {
  display: inline-block;
  margin-top: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--demo-primary);
  text-decoration: none;
}

.row-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  button {
    border: 1px solid var(--demo-line);
    background: #fff;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    cursor: pointer;
  }
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
