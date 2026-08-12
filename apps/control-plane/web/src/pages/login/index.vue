<template>
  <div class="login-wrapper">
    <login-header :is-admin="isAdminLogin"/>

    <div class="login-container">
      <div class="title-container">
        <h1 class="title margin-no"></h1>
        <h1 class="title">{{ isAdminLogin ? 'YinoVapi Operator' : 'YinoVapi' }}</h1>
        <div class="sub-title"></div>
      </div>

      <login v-if="type === 'login'" :is-admin="isAdminLogin"/>
      <tdesign-setting/>
    </div>

    <footer class="copyright"></footer>
  </div>
</template>
<script>
export default {
  name: 'LoginIndex',
};
</script>
<script setup>
import {ref, computed} from 'vue';
import {useRoute} from 'vue-router';

import TdesignSetting from '@/layouts/setting.vue';
import LoginHeader from './components/Header.vue';
import Login from './components/Login.vue';

const type = ref('login');
const route = useRoute();

const isAdminLogin = computed(() => route.path === '/admin/login');
</script>

<style lang="less" scoped>
@import './index.less';
</style>
