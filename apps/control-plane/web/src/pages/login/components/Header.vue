<template>
  <header class="login-header">
    <img src="@/assets/login_026.png" class="logo" alt="logo" />
    <div class="operations-container">
      <t-button theme="default" shape="square" variant="text" @click="toggleSettingPanel">
        <t-icon name="setting" class="icon"/>
      </t-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import {useSettingStore} from '@/store';

defineProps<{ isAdmin?: boolean }>();

const settingStore = useSettingStore();
const toggleSettingPanel = () => {
  settingStore.updateConfig({
    showSettingPanel: true,
  });
};
</script>

<style lang="less" scoped>
.login-header {
  padding: 0 var(--td-comp-paddingLR-xl);
  display: flex;
  justify-content: space-between;
  align-items: center;
  backdrop-filter: blur(10px);
  color: var(--td-text-color-primary);
  height: var(--td-comp-size-xxxl);

  .logo {
    width: 500px;
    height: 100px;
    object-fit: contain;
    margin-top: 130px;
    margin-left: 30px;
    padding-right: 100px;
  }

  .operations-container {
    display: flex;
    align-items: center;

    .t-button {
      margin-left: var(--td-comp-margin-l);
    }
  }
}
</style>
