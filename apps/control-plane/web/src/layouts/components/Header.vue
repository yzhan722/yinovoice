<template>
  <div :class="layoutCls">
    <t-head-menu :class="menuCls" :theme="menuTheme" expand-type="popup" :value="active">
      <template #logo>
        <span v-if="showLogo" class="header-logo-container">
<!--          <logo-full class="t-logo" />-->
          <img src="@/assets/login_026.png" class="logo t-logo" alt="logo" />
        </span>
        <div v-else class="header-operate-left">
          <t-button theme="default" shape="square" variant="text" @click="changeCollapsed">
            <t-icon class="collapsed-icon" name="view-list" />
          </t-button>
          <span class="mobile-brand">YinoVapi</span>
        </div>
      </template>
      <template v-if="layout !== 'side'" #default>
        <menu-content class="header-menu" :nav-data="menu" />
      </template>
      <template #operations>
        <div class="operations-container">
          <!-- 搜索框 -->
<!--          <search v-if="layout !== 'side'" :layout="layout" />-->

          <!-- 全局通知 -->
<!--          <notice />-->

<!--          <t-dropdown trigger="click">-->
<!--            <t-button theme="default" shape="square" variant="text">-->
<!--              <translate-icon />-->
<!--            </t-button>-->
<!--            <t-dropdown-menu>-->
<!--              <t-dropdown-item v-for="(lang, index) in langList" :key="index" :value="lang.value" @click="changeLang">{{-->
<!--                lang.content-->
<!--              }}</t-dropdown-item></t-dropdown-menu-->
<!--            >-->
<!--          </t-dropdown>-->
          <t-dropdown :min-column-width="120" trigger="click">
            <template #dropdown>
              <t-dropdown-menu>
<!--                <t-dropdown-item class="operations-dropdown-container-item" @click="handleNav('/user/index')">-->
<!--                  <user-circle-icon />{{ $t('layout.header.user') }}-->
<!--                </t-dropdown-item>-->
                <t-dropdown-item class="operations-dropdown-container-item" @click="handleLogout">
                  <poweroff-icon />{{ $t('layout.header.signOut') }}
                </t-dropdown-item>
              </t-dropdown-menu>
            </template>
            <t-button class="header-user-btn" theme="default" variant="text">
              <template #icon>
                <t-icon class="header-user-avatar" name="user-circle" />
              </template>
              <div class="header-user-account">{{ displayAccount }}</div>
              <template #suffix><chevron-down-icon /></template>
            </t-button>
          </t-dropdown>
          <t-tooltip placement="bottom" :content="$t('layout.header.setting')">
            <t-button theme="default" shape="square" variant="text" @click="toggleSettingPanel">
              <setting-icon />
            </t-button>
          </t-tooltip>
        </div>
      </template>
    </t-head-menu>
  </div>
</template>

<script setup lang="ts">
import { ChevronDownIcon, PoweroffIcon, SettingIcon, TranslateIcon, UserCircleIcon } from 'tdesign-icons-vue-next';
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LogoFull from '@/assets/login_026.png';
import { prefix } from '@/config/global';
import { langList } from '@/locales/index';
import { useLocale } from '@/locales/useLocale';
import { getActive } from '@/router';
import { useSettingStore, useUserStore } from '@/store';
import type { MenuRoute } from '@/types/interface';
//@ts-ignore
import {UserBasicService} from "@/api/UserBasicService";
import MenuContent from './MenuContent.vue';
import Notice from './Notice.vue';
// import Search from './Search.vue';
const $UserBasicService = new UserBasicService();
const props = defineProps({
  theme: {
    type: String,
    default: 'light',
  },
  layout: {
    type: String,
    default: 'top',
  },
  showLogo: {
    type: Boolean,
    default: true,
  },
  menu: {
    type: Array as PropType<MenuRoute[]>,
    default: (): MenuRoute[] => [],
  },
  isFixed: {
    type: Boolean,
    default: false,
  },
  isCompact: {
    type: Boolean,
    default: false,
  },
  maxLevel: {
    type: Number,
    default: 3,
  },
});

const router = useRouter();
const route = useRoute();
const settingStore = useSettingStore();
const user = useUserStore();

// 获取管理员token的辅助函数
const getAdminToken = () => {
  try {
    const adminTokenData = sessionStorage.getItem('adminToken');
    if (adminTokenData) {
      const data = JSON.parse(adminTokenData);
      // 检查token是否过期
      if (data.expireTime && data.expireTime > Date.now()) {
        return data.token;
      } else {
        // token已过期，清除
        sessionStorage.removeItem('adminToken');
        return '';
      }
    }
    return '';
  } catch (e) {
    return '';
  }
};

// 显示账号信息（管理员账号或普通用户名）
const displayAccount = computed((): string => {
  // 如果有管理员token，显示管理员账号
  const adminToken = getAdminToken();
  if (adminToken) {
    return user.adminInfo?.account || '管理员';
  }
  // 否则显示普通用户名
  return user.userInfo.name || '';
});

const toggleSettingPanel = () => {
  settingStore.updateConfig({
    showSettingPanel: true,
  });
};

const active = computed(() => getActive(route));

const layoutCls = computed(() => [`${prefix}-header-layout`]);

const menuCls = computed(() => {
  const { isFixed, layout, isCompact } = props;
  return [
    {
      [`${prefix}-header-menu`]: !isFixed,
      [`${prefix}-header-menu-fixed`]: isFixed,
      [`${prefix}-header-menu-fixed-side`]: layout === 'side' && isFixed,
      [`${prefix}-header-menu-fixed-side-compact`]: layout === 'side' && isFixed && isCompact,
    },
  ];
});
const menuTheme = computed(() => props.theme as 'light' | 'dark');

// 切换语言
const { changeLocale } = useLocale();
const changeLang = ({ value: lang }: { value: string }) => {
  changeLocale(lang);
};

const changeCollapsed = () => {
  settingStore.updateConfig({
    isSidebarCompact: !settingStore.isSidebarCompact,
  });
};

const handleNav = (url: string) => {
  router.push(url);
};

const handleLogout = () => {
  user.adminLogout();
  router.push({
    path: '/login',
    query: {redirect: encodeURIComponent(route.fullPath)},
  });
};

</script>
<style lang="less" scoped>
.@{starter-prefix}-header {
  &-menu-fixed {
    position: fixed;
    top: 0;
    z-index: 1001;

    :deep(.t-head-menu__inner) {
      padding-right: var(--td-comp-margin-xl);
    }

    &-side {
      left: 232px;
      right: 0;
      z-index: 10;
      width: auto;
      transition: all 0.3s;

      &-compact {
        left: 64px;
      }
    }
  }

  &-logo-container {
    cursor: pointer;
    display: inline-flex;
  }
}

.header-menu {
  flex: 1 1 1;
  display: inline-flex;

  :deep(.t-menu__item) {
    min-width: unset;
  }
}

.operations-container {
  display: flex;
  align-items: center;

  .t-popup__reference {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .t-button {
    margin-left: var(--td-comp-margin-l);
  }
}

.header-operate-left {
  display: flex;
  align-items: center;
  line-height: 0;
  padding-left: 8px;
  gap: 4px;
}

.mobile-brand {
  display: none;
  font-size: 16px;
  font-weight: 800;
  color: var(--demo-primary, #5b4dff);
  margin-left: 4px;
  line-height: 1;
  font-family: var(--demo-font, inherit);
}

@media (max-width: 768px) {
  .mobile-brand {
    display: inline-block;
  }

  .header-logo-container {
    margin-left: 4px;
    padding: 8px 10px;
    min-width: 0;
    max-width: 140px;
    height: 48px;
  }

  .header-user-btn {
    padding-left: 4px !important;
    padding-right: 4px !important;
  }
}

.header-logo-container {
  box-sizing: border-box;
  width: auto;
  min-width: 120px;
  max-width: 200px;
  height: 56px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 8px;
  padding: 10px 16px; /* logo safe area */
  color: var(--td-text-color-primary);

  .t-logo {
    display: block;
    width: auto;
    max-width: 100%;
    height: auto;
    max-height: 32px;
    min-height: 24px;
    object-fit: contain;

    &:hover {
      cursor: pointer;
    }
  }

  &:hover {
    cursor: pointer;
  }
}

.header-user-account {
  display: inline-flex;
  align-items: center;
  color: var(--td-text-color-primary);
}

:deep(.t-head-menu__inner) {
  border-bottom: 1px solid var(--td-component-stroke);
}

.t-menu--light {
  .header-user-account {
    color: var(--td-text-color-primary);
  }
}

.t-menu--dark {
  .t-head-menu__inner {
    border-bottom: 1px solid var(--td-gray-color-10);
  }

  .header-user-account {
    color: rgb(255 255 255 / 55%);
  }
}

.operations-dropdown-container-item {
  width: 100%;
  display: flex;
  align-items: center;

  :deep(.t-dropdown__item-text) {
    display: flex;
    align-items: center;
  }

  .t-icon {
    font-size: var(--td-comp-size-xxxs);
    margin-right: var(--td-comp-margin-s);
  }

  :deep(.t-dropdown__item) {
    width: 100%;
    margin-bottom: 0;
  }

  &:last-child {
    :deep(.t-dropdown__item) {
      margin-bottom: 8px;
    }
  }
}
</style>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="less">
.operations-dropdown-container-item {
  .t-dropdown__item-text {
    display: flex;
    align-items: center;
  }
}
</style>
