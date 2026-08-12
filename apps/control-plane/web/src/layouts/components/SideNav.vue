<template>
  <div :class="sideNavCls">
    <div
      v-if="isMobile && mobileDrawerOpen"
      class="mobile-nav-mask"
      @click="closeMobileDrawer"
    />
    <t-menu
      :class="menuCls"
      :theme="theme"
      :value="active"
      :collapsed="menuCollapsed"
      :default-expanded="defaultExpanded"
    >
      <template #logo>
        <a
          v-if="showLogo"
          :class="[`${prefix}-side-nav-logo-wrapper`, { collapsed: menuCollapsed }]"
          href="javascript:void(0)"
          aria-label="YinoVapi 首页"
          @click.prevent="goHome"
        >
          <img
            src="@/assets/login_026.png"
            :class="`${prefix}-side-nav-logo-img`"
            alt="YinoVapi"
          />
        </a>
      </template>

      <div v-if="!menuCollapsed" class="nav-group-label">功能导航</div>
      <menu-content :nav-data="menu" />
      <template #operations>
        <span v-if="!menuCollapsed" class="version-container">YinoVapi Demo</span>
      </template>
    </t-menu>
    <div
      v-if="!isMobile"
      :class="`${prefix}-side-nav-placeholder${collapsed ? '-hidden' : ''}`"
    />
  </div>
</template>

<script setup lang="ts">
import union from 'lodash/union';
import type { PropType } from 'vue';
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { prefix } from '@/config/global';
import { getActive, getRoutesExpanded } from '@/router';
import { useSettingStore } from '@/store';
import type { MenuRoute } from '@/types/interface';

import MenuContent from './MenuContent.vue';

const MOBILE_MAX = 768;
const COMPACT_MAX = 991;

const props = defineProps({
  menu: {
    type: Array as PropType<MenuRoute[]>,
    default: () => [],
  },
  showLogo: {
    type: Boolean as PropType<boolean>,
    default: true,
  },
  isFixed: {
    type: Boolean as PropType<boolean>,
    default: true,
  },
  layout: {
    type: String as PropType<string>,
    default: '',
  },
  headerHeight: {
    type: String as PropType<string>,
    default: '64px',
  },
  theme: {
    type: String as PropType<'light' | 'dark'>,
    default: 'light',
  },
  isCompact: {
    type: Boolean as PropType<boolean>,
    default: false,
  },
});

const settingStore = useSettingStore();
const collapsed = computed(() => settingStore.isSidebarCompact);
const isMobile = ref(false);
/** On mobile: drawer open when sidebar is NOT compact */
const mobileDrawerOpen = computed(() => isMobile.value && !collapsed.value);
/** Collapsed icon rail on tablet; on mobile drawer uses expanded menu when open */
const menuCollapsed = computed(() => {
  if (isMobile.value) return false; // drawer always shows full labels when visible
  return collapsed.value;
});

const route = useRoute();
const active = computed(() => getActive(route));

const defaultExpanded = computed(() => {
  const path = getActive(route);
  const parentPath = path.substring(0, path.lastIndexOf('/'));
  const expanded = getRoutesExpanded();
  return union(expanded, parentPath === '' ? [] : [parentPath]);
});

const sideNavCls = computed(() => {
  const { isCompact } = props;
  return [
    `${prefix}-sidebar-layout`,
    {
      [`${prefix}-sidebar-compact`]: isCompact && !isMobile.value,
      'is-mobile': isMobile.value,
      'is-mobile-open': mobileDrawerOpen.value,
    },
  ];
});

const menuCls = computed(() => {
  const { showLogo, isFixed, layout } = props;
  return [
    `${prefix}-side-nav`,
    {
      [`${prefix}-side-nav-no-logo`]: !showLogo,
      [`${prefix}-side-nav-no-fixed`]: !isFixed,
      [`${prefix}-side-nav-mix-fixed`]: layout === 'mix' && isFixed,
      'mobile-drawer': isMobile.value,
      'mobile-drawer--open': mobileDrawerOpen.value,
    },
  ];
});

const router = useRouter();

function syncViewport() {
  const w = window.innerWidth;
  const mobile = w <= MOBILE_MAX;
  isMobile.value = mobile;
  if (mobile) {
    // keep drawer closed by default on mobile
    settingStore.updateConfig({ isSidebarCompact: true });
  } else {
    settingStore.updateConfig({ isSidebarCompact: w <= COMPACT_MAX });
  }
}

function closeMobileDrawer() {
  settingStore.updateConfig({ isSidebarCompact: true });
}

onMounted(() => {
  syncViewport();
  window.addEventListener('resize', syncViewport);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport);
});

watch(
  () => route.fullPath,
  () => {
    if (isMobile.value) closeMobileDrawer();
  },
);

const goHome = () => {
  router.push('/user/dashboard');
  if (isMobile.value) closeMobileDrawer();
};
</script>

<style lang="less" scoped>
.tdesign-starter-side-nav-logo-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 100%;
  min-height: 64px;
  padding: 12px 16px;
  text-decoration: none;

  &.collapsed {
    padding: 12px 8px;
    min-height: 56px;
  }
}

.tdesign-starter-side-nav-logo-img {
  display: block;
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: 40px;
  min-height: 28px;
  object-fit: contain;
  object-position: center;
}

:deep(.t-default-menu__inner .t-menu__logo:not(:empty)) {
  height: auto !important;
  min-height: 64px;
  border-bottom: 1px solid var(--demo-line);
}

.nav-group-label {
  padding: 8px 16px 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--demo-muted);
}

.version-container {
  font-size: 11px;
  color: var(--demo-muted);
}

:deep(.t-default-menu .t-menu__item) {
  height: 44px;
  margin: 2px 8px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 650;
  font-family: var(--demo-font);
}

:deep(.t-default-menu .t-menu__item.t-is-active) {
  font-weight: 800;
  background: var(--demo-primary-soft) !important;
  color: var(--demo-primary) !important;
}

:deep(.t-default-menu) {
  background: #fff !important;
  border-right: 1px solid var(--demo-line);
}

:deep(.t-default-menu .t-menu__item:hover:not(.t-is-active)) {
  background: #f8f8fc !important;
}

.mobile-nav-mask {
  position: fixed;
  inset: 0;
  z-index: 190;
  background: rgba(0, 0, 0, 0.45);
}

:deep(.t-default-menu.mobile-drawer) {
  position: fixed !important;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 200;
  width: min(80vw, 280px) !important;
  transform: translateX(-105%);
  transition: transform 0.25s ease;
  box-shadow: none;
}

:deep(.t-default-menu.mobile-drawer.mobile-drawer--open) {
  transform: translateX(0);
  box-shadow: 8px 0 24px rgba(0, 0, 0, 0.12);
}

@media (max-width: 768px) {
  .is-mobile:not(.is-mobile-open) {
    width: 0;
    min-width: 0;
    overflow: visible;
  }
}
</style>
