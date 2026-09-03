<template>
  <div class="demo-page">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">排期设置</h1>
        <p class="demo-page-sub">单资源营业时间与服务项目 · 以实例本地时区生成可预约时段</p>
      </div>
    </div>

    <section class="demo-card block">
      <label>
        实例
        <select v-model="instanceId" data-testid="scheduling-instance" @change="reload">
          <option value="" disabled>选择实例</option>
          <option v-for="item in instances" :key="item.id" :value="item.id">
            {{ item.display_name || item.id }}
          </option>
        </select>
      </label>
      <form class="grid" @submit.prevent="saveProfile">
        <label>时区<input v-model="profile.timezone" required data-testid="sched-timezone" /></label>
        <label>槽位分钟<input v-model.number="profile.slotIntervalMinutes" type="number" min="5" max="60" /></label>
        <label>最少提前分钟<input v-model.number="profile.minimumNoticeMinutes" type="number" min="0" /></label>
        <label>可预约天数<input v-model.number="profile.bookingHorizonDays" type="number" min="1" max="365" /></label>
        <button type="submit" class="primary">保存排期配置</button>
      </form>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </section>

    <section class="demo-card block">
      <h2>服务项目</h2>
      <form class="grid" @submit.prevent="addOffering">
        <label>名称<input v-model="offering.name" required data-testid="offering-name" /></label>
        <label>时长（分钟）<input v-model.number="offering.durationMinutes" type="number" min="5" required /></label>
        <button type="submit" class="primary">新增项目</button>
      </form>
      <ul class="plain">
        <li v-for="item in offerings" :key="item.id">{{ item.name }} · {{ item.duration_minutes }} 分钟</li>
      </ul>
    </section>

    <section class="demo-card block">
      <h2>可预约预览</h2>
      <form class="grid" @submit.prevent="loadSlots">
        <label>
          项目
          <select v-model="previewOfferingId" required>
            <option value="" disabled>选择项目</option>
            <option v-for="item in offerings" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label>从<input v-model="dateFrom" type="date" required /></label>
        <label>到<input v-model="dateTo" type="date" required /></label>
        <button type="submit" class="primary">查询档期</button>
      </form>
      <p class="meta">{{ slots.length }} 个可预约时段</p>
      <ul class="plain" data-testid="availability-list">
        <li v-for="slot in slots.slice(0, 12)" :key="slot.slot_start_utc">
          {{ slot.slot_start_local }} → {{ slot.slot_end_local }}
        </li>
      </ul>
    </section>

    <section class="demo-card block">
      <h2>预约通知</h2>
      <p class="meta">新预约或回拨会发到这个邮箱。未配置 SMTP 时只保存设置、不发信。</p>
      <form class="grid" data-testid="notify-form" @submit.prevent="saveNotify">
        <label>通知邮箱<input v-model="notifyEmail" type="email" data-testid="notify-email" /></label>
        <label class="check">
          <input v-model="notifyEnabled" type="checkbox" data-testid="notify-enabled" />
          启用通知
        </label>
        <button type="submit" class="primary" data-testid="save-notify">保存通知设置</button>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import { RealtimeVoiceService, TenantNotificationService, TenantSchedulingService } from '@/api/platform';

const voice = new RealtimeVoiceService();
const scheduling = new TenantSchedulingService();
const notifications = new TenantNotificationService();
const instances = ref<any[]>([]);
const instanceId = ref('');
const offerings = ref<any[]>([]);
const slots = ref<any[]>([]);
const error = ref('');
const notifyEmail = ref('');
const notifyEnabled = ref(true);
const profile = ref({
  timezone: 'Australia/Melbourne',
  slotIntervalMinutes: 15,
  minimumNoticeMinutes: 60,
  bookingHorizonDays: 60,
});
const offering = ref({ name: '洁牙', durationMinutes: 30 });
const previewOfferingId = ref('');

function isoDate(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Default preview window: today through the next 6 days.
const dateFrom = ref(isoDate(0));
const dateTo = ref(isoDate(6));

async function reload() {
  if (!instanceId.value) return;
  error.value = '';
  try {
    const listed = await scheduling.listOfferings(instanceId.value);
    offerings.value = Array.isArray(listed) ? listed : listed.items || [];
    if (offerings.value[0] && !previewOfferingId.value) {
      previewOfferingId.value = offerings.value[0].id;
    }
    try {
      const loaded = await scheduling.getProfile(instanceId.value);
      profile.value.timezone = loaded.timezone;
      profile.value.slotIntervalMinutes = loaded.slot_interval_minutes;
      profile.value.minimumNoticeMinutes = loaded.minimum_notice_minutes;
      profile.value.bookingHorizonDays = loaded.booking_horizon_days;
    } catch (_) {
      /* first-time profile */
    }
  } catch (err: any) {
    error.value = err?.message || '无法加载排期';
  }
}

async function saveProfile() {
  if (!instanceId.value) return;
  try {
    await scheduling.putProfile(instanceId.value, profile.value);
    await scheduling.putHours(instanceId.value, weekdayHours());
    MessagePlugin.success('排期已保存');
    await reload();
  } catch (err: any) {
    error.value = err?.message || '保存失败';
  }
}

async function addOffering() {
  if (!instanceId.value) return;
  try {
    await scheduling.createOffering({
      instanceId: instanceId.value,
      name: offering.value.name,
      durationMinutes: offering.value.durationMinutes,
    });
    await reload();
  } catch (err: any) {
    error.value = err?.message || '创建项目失败';
  }
}

async function loadSlots() {
  if (!instanceId.value || !previewOfferingId.value) return;
  const page = await scheduling.listAvailability({
    instanceId: instanceId.value,
    offeringId: previewOfferingId.value,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
  });
  slots.value = page.items || [];
}

async function loadNotify() {
  try {
    const settings = await notifications.get();
    notifyEmail.value = settings.email || '';
    notifyEnabled.value = settings.enabled !== false;
  } catch (_) {
    /* first-time settings */
  }
}

async function saveNotify() {
  try {
    await notifications.put({
      email: notifyEmail.value,
      enabled: notifyEnabled.value,
    });
    MessagePlugin.success('通知设置已保存');
  } catch (err: any) {
    error.value = err?.message || '保存通知失败';
  }
}

function weekdayHours() {
  const hours: Array<Record<string, unknown>> = [];
  for (let weekday = 0; weekday < 5; weekday += 1) {
    hours.push({ weekday, start_local: '09:00', end_local: '12:00', enabled: true });
    hours.push({ weekday, start_local: '13:00', end_local: '17:00', enabled: true });
  }
  return hours;
}

onMounted(async () => {
  await loadNotify();
  const services = await voice.listCustomerServices();
  instances.value = services.items || [];
  if (instances.value[0]) {
    instanceId.value = instances.value[0].id;
    await reload();
  }
});
</script>

<style scoped lang="less">
.page-head { margin-bottom: 14px; }
.block { padding: 14px; margin-bottom: 14px; }
.grid {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  label { display: grid; gap: 4px; font-size: 12px; color: var(--demo-muted); }
  input, select { padding: 8px 10px; border: 1px solid var(--demo-line); border-radius: 6px; }
}
.primary {
  border: 0;
  border-radius: 7px;
  padding: 9px 14px;
  background: var(--demo-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  justify-self: start;
}
.error { color: #c62828; }
.plain { margin: 10px 0 0; padding-left: 18px; }
.meta { color: var(--demo-muted); font-size: 12px; }
.check { display: flex; align-items: center; gap: 8px; }
h2 { margin: 0; font-size: 15px; }
</style>
