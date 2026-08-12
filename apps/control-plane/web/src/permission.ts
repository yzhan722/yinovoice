import 'nprogress/nprogress.css';

import NProgress from 'nprogress';
import { RouteRecordRaw } from 'vue-router';

import router from '@/router';
import { getPermissionStore, useUserStore } from '@/store';
import { PAGE_NOT_FOUND_ROUTE } from '@/utils/route/constant';

NProgress.configure({ showSpinner: false });

function getAdminToken(): string {
  try {
    const raw = sessionStorage.getItem('adminToken');
    if (!raw) return '';
    const data = JSON.parse(raw);
    if (data.expireTime && data.expireTime > Date.now()) return data.token || '';
    sessionStorage.removeItem('adminToken');
  } catch (_) {}
  return '';
}

function getUserToken(): string {
  try {
    const raw = sessionStorage.getItem('userToken');
    if (!raw) return '';
    const data = JSON.parse(raw);
    if (data.expireTime && data.expireTime > Date.now()) return data.token || '';
    sessionStorage.removeItem('userToken');
  } catch (_) {}
  return '';
}

router.beforeEach(async (to, from, next) => {
  NProgress.start();

  const permissionStore = getPermissionStore();
  const { whiteListRouters } = permissionStore;
  const userStore = useUserStore();

  if (whiteListRouters.indexOf(to.path) !== -1) {
    next();
    NProgress.done();
    return;
  }

  const isAdminRoute = to.path.startsWith('/admin');
  const adminToken = getAdminToken();
  const userToken = getUserToken();

  if (isAdminRoute) {
    if (!adminToken) {
      next({ path: '/admin/login', query: { redirect: encodeURIComponent(to.fullPath) } });
      NProgress.done();
      return;
    }
    try {
      await userStore.getAdminInfo();
      const { asyncRoutes } = permissionStore;
      if (!asyncRoutes || asyncRoutes.length === 0) {
        const routeList = await permissionStore.buildAsyncRoutes('admin');
        routeList.forEach((item: RouteRecordRaw) => router.addRoute(item));
        next(to.name === PAGE_NOT_FOUND_ROUTE.name
          ? { path: to.fullPath, replace: true, query: to.query }
          : { path: to.fullPath, replace: true, query: to.query });
        NProgress.done();
        return;
      }
      next();
    } catch (_) {
      next({ path: '/admin/login', query: { redirect: encodeURIComponent(to.fullPath) } });
      NProgress.done();
    }
    return;
  }

  // 用户路由（非 /admin 且不在白名单）
  if (!userToken) {
    next({ path: '/login', query: { redirect: encodeURIComponent(to.fullPath) } });
    NProgress.done();
    return;
  }
  try {
    await userStore.getUserProfile();
    const { asyncRoutes } = permissionStore;
    if (!asyncRoutes || asyncRoutes.length === 0) {
      const routeList = await permissionStore.buildAsyncRoutes('user');
      routeList.forEach((item: RouteRecordRaw) => router.addRoute(item));
      next(to.name === PAGE_NOT_FOUND_ROUTE.name
        ? { path: to.fullPath, replace: true, query: to.query }
        : { path: to.fullPath, replace: true, query: to.query });
      NProgress.done();
      return;
    }
    next();
  } catch (_) {
    next({ path: '/login', query: { redirect: encodeURIComponent(to.fullPath) } });
    NProgress.done();
  }
});

router.afterEach((to) => {
  if (to.path === '/login') {
    const userStore = useUserStore();
    const permissionStore = getPermissionStore();
    userStore.userLogout();
    permissionStore.restoreRoutes();
  } else if (to.path === '/admin/login') {
    const userStore = useUserStore();
    const permissionStore = getPermissionStore();
    userStore.adminLogout();
    permissionStore.restoreRoutes();
  }
  NProgress.done();
});
