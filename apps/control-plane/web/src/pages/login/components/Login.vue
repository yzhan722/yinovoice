<template>
  <t-form
      ref="form"
      :class="['item-container', 'login-password']"
      :data="formData"
      :rules="FORM_RULES"
      label-width="0"
      @submit="onSubmit"
  >
    <t-alert
      v-if="shellHint"
      theme="info"
      :message="shellHint"
      style="margin-bottom: 16px"
    />
    <t-form-item name="account">
      <t-input v-model="formData.account" size="large" placeholder="请输入账号" clearable>
        <template #prefix-icon>
          <t-icon name="user"/>
        </template>
      </t-input>
    </t-form-item>

    <t-form-item name="password">
      <t-input
          v-model="formData.password"
          size="large"
          :type="showPsw ? 'text' : 'password'"
          clearable
          placeholder="请输入密码"
      >
        <template #prefix-icon>
          <t-icon name="lock-on"/>
        </template>
        <template #suffix-icon>
          <t-icon :name="showPsw ? 'browse' : 'browse-off'" @click="showPsw = !showPsw"/>
        </template>
      </t-input>
    </t-form-item>

    <t-form-item class="btn-container">
      <t-button block size="large" type="submit">登录</t-button>
    </t-form-item>
  </t-form>
</template>

<script setup lang="ts">
import type {FormInstanceFunctions, SubmitContext} from 'tdesign-vue-next';
import {MessagePlugin} from 'tdesign-vue-next';
import {computed, ref} from 'vue';
import {useRoute, useRouter} from 'vue-router';

import {useUserStore} from '@/store';
import {SHELL_ACCOUNTS, shellMockEnabled} from '@/mocks/shell';

defineProps<{ isAdmin?: boolean }>();

const userStore = useUserStore();
const route = useRoute();
const router = useRouter();

const isAdminLogin = computed(
  () => (route.meta?.isAdminLogin ?? route.path === '/admin/login') as boolean,
);

const shellHint = computed(() => {
  if (isAdminLogin.value) {
    if (!shellMockEnabled()) return '';
    return `演示账号：${SHELL_ACCOUNTS.operator.account} / ${SHELL_ACCOUNTS.operator.password}（运营端非本阶段重点）`;
  }
  return `演示账号：${SHELL_ACCOUNTS.tenant.account} / ${SHELL_ACCOUNTS.tenant.password} · 租户工作台`;
});

const FORM_RULES: any = {
  account: [{required: true, message: '请输入账号', type: 'error'}],
  password: [{required: true, message: '请输入密码', type: 'error'}],
};

const form = ref<FormInstanceFunctions>();
const formData = ref({
  account: shellMockEnabled()
    ? (route.path === '/admin/login' ? SHELL_ACCOUNTS.operator.account : SHELL_ACCOUNTS.tenant.account)
    : '',
  password: shellMockEnabled()
    ? (route.path === '/admin/login' ? SHELL_ACCOUNTS.operator.password : SHELL_ACCOUNTS.tenant.password)
    : '',
});
const showPsw = ref(false);

const onSubmit = async (ctx: SubmitContext) => {
  if (ctx.validateResult !== true) return;
  try {
    if (isAdminLogin.value) {
      await userStore.adminLogin({ account: formData.value.account, password: formData.value.password });
      MessagePlugin.success('登录成功');
      const redirect = route.query.redirect as string;
      router.push(redirect ? decodeURIComponent(redirect) : '/admin/dashboard');
    } else {
      await userStore.userLogin({ account: formData.value.account, password: formData.value.password });
      MessagePlugin.success('登录成功');
      const redirect = route.query.redirect as string;
      router.push(redirect ? decodeURIComponent(redirect) : '/user/dashboard');
    }
  } catch (e: any) {
    console.error(e);
    MessagePlugin.error(e?.message || '登录失败');
  }
};
</script>

<style lang="less" scoped>
@import '../index.less';
</style>
