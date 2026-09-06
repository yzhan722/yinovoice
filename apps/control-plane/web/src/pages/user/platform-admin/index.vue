<template>
  <div class="demo-page">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">平台管理</h1>
        <p class="demo-page-sub">租户、操作员账号与租户视角切换 · 仅平台管理员可见</p>
      </div>
    </div>

    <section v-if="actingOther" class="demo-card block acting" role="status" data-testid="acting-banner">
      <span>
        当前正以租户 <strong>{{ actingTenantLabel }}</strong> 的视角操作其他页面（实例、通话、排期均属于该租户）。
      </span>
      <button type="button" class="ghost" data-testid="reset-acting" @click="resetActing">返回本租户</button>
    </section>

    <section class="demo-card block">
      <h2>租户</h2>
      <form class="grid inline" @submit.prevent="createTenant">
        <label>租户名称<input v-model="newTenant.name" required maxlength="120" data-testid="tenant-name" /></label>
        <label>
          数据区域
          <select v-model="newTenant.homeRegion">
            <option value="cn-mainland">cn-mainland</option>
            <option value="ap-southeast">ap-southeast</option>
          </select>
        </label>
        <button type="submit" class="primary" data-testid="create-tenant">新建租户</button>
      </form>
      <table class="table" data-testid="tenant-table">
        <thead>
          <tr><th>名称</th><th>租户 ID</th><th>区域</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-if="tenants.length === 0"><td colspan="5" class="meta">暂无租户</td></tr>
          <tr v-for="tenant in tenants" :key="tenant.id" :class="{ current: tenant.id === selectedTenantId }">
            <td>{{ tenant.name }}</td>
            <td><code>{{ tenant.id }}</code></td>
            <td>{{ tenant.home_region }}</td>
            <td>{{ tenant.status === 'active' ? '启用' : '停用' }}</td>
            <td class="actions">
              <button type="button" class="ghost" @click="selectTenant(tenant.id)">管理账号</button>
              <button
                type="button"
                class="ghost"
                :disabled="tenant.id === actingTenantId"
                :data-testid="`act-as-${tenant.id}`"
                @click="actAs(tenant)"
              >
                {{ tenant.id === actingTenantId ? '当前视角' : '进入租户视角' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="demo-card block">
      <h2>操作员账号<span v-if="selectedTenant" class="meta"> · {{ selectedTenant.name }}</span></h2>
      <p v-if="!selectedTenantId" class="meta">先在上方选择一个租户。</p>
      <template v-else>
        <form class="grid inline" @submit.prevent="createUser">
          <label>账号<input v-model="newUser.account" required maxlength="80" data-testid="user-account" /></label>
          <label>昵称<input v-model="newUser.nickname" maxlength="80" /></label>
          <label>初始密码<input v-model="newUser.password" type="text" required minlength="6" data-testid="user-password" /></label>
          <label>
            角色
            <select v-model="newUser.role">
              <option value="tenant_operator">租户操作员</option>
              <option value="platform_admin">平台管理员</option>
            </select>
          </label>
          <button type="submit" class="primary" data-testid="create-user">新建账号</button>
        </form>
        <table class="table" data-testid="user-table">
          <thead>
            <tr><th>账号</th><th>昵称</th><th>角色</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-if="users.length === 0"><td colspan="5" class="meta">该租户暂无账号</td></tr>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.account }}</td>
              <td>{{ user.nickname }}</td>
              <td>{{ user.role === 'platform_admin' ? '平台管理员' : '租户操作员' }}</td>
              <td>{{ user.status === 'active' ? '启用' : '停用' }}</td>
              <td class="actions">
                <button type="button" class="ghost" @click="resetPassword(user)">重置密码</button>
                <button type="button" class="ghost" @click="toggleStatus(user)">
                  {{ user.status === 'active' ? '停用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </template>
    </section>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { PlatformAdminService } from '@/api/platform/AdminService';
import {
  isActingAsOtherTenant,
  readStoredTenantId,
  resetActingTenant,
  switchActingTenant,
} from '@/api/platform/platformSession';

type Tenant = { id: string; name: string; home_region: string; status: string };
type Operator = {
  id: string;
  account: string;
  nickname: string;
  role: string;
  status: string;
  tenant_id: string;
};

const admin = new PlatformAdminService();
const router = useRouter();

const tenants = ref<Tenant[]>([]);
const users = ref<Operator[]>([]);
const selectedTenantId = ref('');
const error = ref('');
const actingTenantId = ref(readStoredTenantId(''));
const actingOther = ref(isActingAsOtherTenant());
const newTenant = ref({ name: '', homeRegion: 'cn-mainland' });
const newUser = ref({ account: '', nickname: '', password: '', role: 'tenant_operator' });

const selectedTenant = computed(() => tenants.value.find((t) => t.id === selectedTenantId.value));
const actingTenantLabel = computed(
  () => tenants.value.find((t) => t.id === actingTenantId.value)?.name || actingTenantId.value,
);

async function loadTenants() {
  error.value = '';
  try {
    tenants.value = await admin.listTenants();
    if (!selectedTenantId.value && tenants.value[0]) {
      await selectTenant(tenants.value[0].id);
    }
  } catch (err: any) {
    error.value = err?.message || '无法加载租户';
  }
}

async function selectTenant(tenantId: string) {
  selectedTenantId.value = tenantId;
  error.value = '';
  try {
    users.value = await admin.listUsers(tenantId);
  } catch (err: any) {
    error.value = err?.message || '无法加载账号';
  }
}

async function createTenant() {
  error.value = '';
  try {
    const created = await admin.createTenant(newTenant.value);
    newTenant.value = { name: '', homeRegion: 'cn-mainland' };
    MessagePlugin.success('租户已创建');
    await loadTenants();
    await selectTenant(created.id);
  } catch (err: any) {
    error.value = err?.message || '创建租户失败';
  }
}

async function createUser() {
  error.value = '';
  try {
    await admin.createUser({ tenantId: selectedTenantId.value, ...newUser.value });
    newUser.value = { account: '', nickname: '', password: '', role: 'tenant_operator' };
    MessagePlugin.success('账号已创建，请把初始密码告知对方');
    await selectTenant(selectedTenantId.value);
  } catch (err: any) {
    error.value = err?.message || '创建账号失败';
  }
}

async function resetPassword(user: Operator) {
  const password = window.prompt(`为 ${user.account} 设置新密码（至少 6 位）`);
  if (!password) return;
  error.value = '';
  try {
    await admin.resetPassword(user.id, password);
    MessagePlugin.success('密码已重置');
  } catch (err: any) {
    error.value = err?.message || '重置密码失败';
  }
}

async function toggleStatus(user: Operator) {
  error.value = '';
  try {
    await admin.setStatus(user.id, user.status === 'active' ? 'disabled' : 'active');
    await selectTenant(selectedTenantId.value);
  } catch (err: any) {
    error.value = err?.message || '更新状态失败';
  }
}

function actAs(tenant: Tenant) {
  switchActingTenant(tenant.id);
  actingTenantId.value = tenant.id;
  actingOther.value = isActingAsOtherTenant();
  MessagePlugin.success(`已切换到租户 ${tenant.name}`);
  void router.push('/user/assistant-settings/index');
}

function resetActing() {
  resetActingTenant();
  actingTenantId.value = readStoredTenantId('');
  actingOther.value = isActingAsOtherTenant();
  MessagePlugin.success('已返回本租户');
}

onMounted(loadTenants);
</script>

<style scoped lang="less">
.page-head { margin-bottom: 14px; }
.block { padding: 14px; margin-bottom: 14px; }
.acting {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #fff8e6;
  border: 1px solid #f3d999;
  color: #76520e;
}
.grid {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  label { display: grid; gap: 4px; font-size: 12px; color: var(--demo-muted); }
  input, select { padding: 8px 10px; border: 1px solid var(--demo-line); border-radius: 6px; }
}
.inline {
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  align-items: end;
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
.ghost {
  border: 1px solid var(--demo-line);
  border-radius: 7px;
  padding: 6px 10px;
  background: #fff;
  cursor: pointer;
  &:disabled { opacity: 0.6; cursor: default; }
}
.table {
  width: 100%;
  margin-top: 12px;
  border-collapse: collapse;
  font-size: 13px;
  th, td { padding: 8px 6px; text-align: left; border-bottom: 1px solid var(--demo-line); }
  th { color: var(--demo-muted); font-weight: 600; }
  code { font-size: 12px; }
  .current td { background: #f5f8ff; }
}
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
.error { color: #c62828; }
.meta { color: var(--demo-muted); font-size: 12px; font-weight: 400; }
h2 { margin: 0; font-size: 15px; }
</style>
