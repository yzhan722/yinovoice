import { useUserStore } from '@/store';

/**
 * Phase-1 Demo menus: keep product modules visible, no real telephony.
 * Call History stays as an integration slot (see docs/CALL_INTEGRATION.md).
 */
export function getMenuList(role?: 'admin' | 'user') {
  const userStore = useUserStore();
  return new Promise((resolve, reject) => {
    const menuList: any[] = [];

    // —— Tenant Demo ——
    menuList.push({
      path: '/user/dashboard',
      component: 'LAYOUT',
      redirect: '/user/dashboard/index',
      name: 'UserDashboard',
      meta: {
        single: true,
        title: { zh_CN: '工作台', en_US: 'Workspace' },
        icon: 'dashboard',
        orderNo: 0,
      },
      children: [
        {
          path: 'index',
          name: 'UserDashboardIndex',
          component: 'user/dashboard/index',
          meta: { title: { zh_CN: '工作台', en_US: 'Workspace' } },
        },
      ],
    });

    menuList.push({
      path: '/user/assistant-settings',
      component: 'LAYOUT',
      redirect: '/user/assistant-settings/index',
      name: 'AssistantSettings',
      meta: {
        single: true,
        title: { zh_CN: '我的实例', en_US: 'My Instances' },
        icon: 'setting',
        orderNo: 1,
      },
      children: [
        {
          path: 'index',
          name: 'AssistantSettingsIndex',
          component: 'user/assistant-settings/index',
          meta: { title: { zh_CN: '我的实例', en_US: 'My Instances' } },
        },
        {
          path: 'detail/:attId',
          name: 'UserAssistantDetail',
          component: 'user/assistant-settings/detail',
          meta: {
            title: { zh_CN: '实例详情', en_US: 'Instance Detail' },
            hideInMenu: true,
          },
        },
      ],
    });

    menuList.push({
      path: '/user/create-instance',
      component: 'LAYOUT',
      redirect: '/user/create-instance/index',
      name: 'UserCreateInstanceRoot',
      meta: {
        single: true,
        title: { zh_CN: '创建实例', en_US: 'Create Instance' },
        icon: 'add',
        orderNo: 2,
        hideInMenu: true,
      },
      children: [
        {
          path: 'index',
          name: 'UserCreateInstance',
          component: 'user/create-instance/index',
          meta: { title: { zh_CN: '创建实例', en_US: 'Create Instance' } },
        },
      ],
    });

    menuList.push({
      path: '/user/realtime-voice',
      component: 'LAYOUT',
      redirect: '/user/realtime-voice/index',
      name: 'UserRealtimeVoice',
      meta: {
        single: true,
        title: { zh_CN: '实时语音', en_US: 'Realtime Voice' },
        icon: 'microphone',
        orderNo: 3,
      },
      children: [
        {
          path: 'index',
          name: 'UserRealtimeVoiceIndex',
          component: 'user/realtime-voice/index',
          meta: { title: { zh_CN: '实时语音', en_US: 'Realtime Voice' } },
        },
      ],
    });

    menuList.push({
      path: '/user/callback-tasks',
      component: 'LAYOUT',
      redirect: '/user/callback-tasks/index',
      name: 'UserCallbackTasks',
      meta: {
        single: true,
        title: { zh_CN: '回拨任务', en_US: 'Callback Tasks' },
        icon: 'task',
        orderNo: 4,
      },
      children: [
        {
          path: 'index',
          name: 'UserCallbackTasksIndex',
          component: 'user/callback-tasks/index',
          meta: { title: { zh_CN: '回拨任务', en_US: 'Callback Tasks' } },
        },
      ],
    });

    menuList.push({
      path: '/user/appointments',
      component: 'LAYOUT',
      redirect: '/user/appointments/index',
      name: 'UserAppointments',
      meta: {
        single: true,
        title: { zh_CN: '预约结果', en_US: 'Appointments' },
        icon: 'calendar',
        orderNo: 5,
      },
      children: [
        {
          path: 'index',
          name: 'UserAppointmentsIndex',
          component: 'user/appointments/index',
          meta: { title: { zh_CN: '预约结果', en_US: 'Appointments' } },
        },
      ],
    });

    // Kept as module slot for upcoming call-system share
    menuList.push({
      path: '/user/call-history',
      component: 'LAYOUT',
      redirect: '/user/call-history/index',
      name: 'CallHistory',
      meta: {
        single: true,
        title: { zh_CN: '通话记录', en_US: 'Call Records' },
        icon: 'call',
        orderNo: 6,
      },
      children: [
        {
          path: 'index',
          name: 'CallHistoryIndex',
          component: 'user/call-history/index',
          meta: { title: { zh_CN: '通话记录', en_US: 'Call Records' } },
        },
        {
          path: 'detail/:id',
          name: 'UserCallHistoryDetail',
          component: 'user/call-history/detail',
          meta: {
            title: { zh_CN: '通话详情', en_US: 'Call Detail' },
            hideInMenu: true,
          },
        },
      ],
    });

    // Knowledge base kept but de-emphasized (lowest among tenant modules)
    menuList.push({
      path: '/user/knowledge-base',
      component: 'LAYOUT',
      redirect: '/user/knowledge-base/index',
      name: 'KnowledgeBase',
      meta: {
        single: true,
        title: { zh_CN: '知识库', en_US: 'Knowledge Base' },
        icon: 'file',
        orderNo: 9,
      },
      children: [
        {
          path: 'index',
          name: 'KnowledgeBaseIndex',
          component: 'user/knowledge-base/index',
          meta: { title: { zh_CN: '知识库', en_US: 'Knowledge Base' } },
        },
      ],
    });

    // Learnova B3 mobile companion screens
    menuList.push({
      path: '/user/planner',
      component: 'LAYOUT',
      redirect: '/user/planner/index',
      name: 'UserPlanner',
      meta: {
        single: true,
        title: { zh_CN: '学习计划', en_US: 'Planner' },
        icon: 'calendar',
        orderNo: 6,
        hideInMenu: true,
      },
      children: [
        {
          path: 'index',
          name: 'UserPlannerIndex',
          component: 'user/planner/index',
          meta: { title: { zh_CN: '学习计划', en_US: 'Planner' } },
        },
      ],
    });

    menuList.push({
      path: '/user/achievements',
      component: 'LAYOUT',
      redirect: '/user/achievements/index',
      name: 'UserAchievements',
      meta: {
        single: true,
        title: { zh_CN: '成就', en_US: 'Achievements' },
        icon: 'secured',
        orderNo: 7,
        hideInMenu: true,
      },
      children: [
        {
          path: 'index',
          name: 'UserAchievementsIndex',
          component: 'user/achievements/index',
          meta: { title: { zh_CN: '成就', en_US: 'Achievements' } },
        },
      ],
    });

    menuList.push({
      path: '/user/celebration',
      component: 'LAYOUT',
      redirect: '/user/celebration/index',
      name: 'UserCelebration',
      meta: {
        single: true,
        title: { zh_CN: '庆祝', en_US: 'Celebration' },
        icon: 'check-circle',
        orderNo: 8,
        hideInMenu: true,
      },
      children: [
        {
          path: 'index',
          name: 'UserCelebrationIndex',
          component: 'user/celebration/index',
          meta: { title: { zh_CN: '庆祝', en_US: 'Celebration' } },
        },
      ],
    });

    menuList.push({
      path: '/user/profile',
      component: 'LAYOUT',
      redirect: '/user/profile/index',
      name: 'UserProfile',
      meta: {
        single: true,
        title: { zh_CN: '我的', en_US: 'Profile' },
        icon: 'user',
        orderNo: 10,
        hideInMenu: true,
      },
      children: [
        {
          path: 'index',
          name: 'UserProfileIndex',
          component: 'user/profile/index',
          meta: { title: { zh_CN: '我的', en_US: 'Profile' } },
        },
      ],
    });

    // —— Operator: phase-1 stub only ——
    menuList.push({
      path: '/admin/dashboard',
      component: 'LAYOUT',
      redirect: '/admin/dashboard/index',
      name: 'AdminDashboard',
      meta: {
        single: true,
        title: { zh_CN: '运营端', en_US: 'Operator' },
        icon: 'dashboard',
        orderNo: 0,
      },
      children: [
        {
          path: 'index',
          name: 'AdminDashboardIndex',
          component: 'admin/dashboard/index',
          meta: { title: { zh_CN: '运营端', en_US: 'Operator' } },
        },
      ],
    });

    menuList.push({
      path: '/admin/call-history',
      component: 'LAYOUT',
      redirect: '/admin/call-history/index',
      name: 'AdminCallHistory',
      meta: {
        single: true,
        title: { zh_CN: '通话记录', en_US: 'Call Records' },
        icon: 'call',
        orderNo: 1,
      },
      children: [
        {
          path: 'index',
          name: 'AdminCallHistoryIndex',
          component: 'admin/call-history/index',
          meta: { title: { zh_CN: '通话记录', en_US: 'Call Records' } },
        },
        {
          path: 'detail/:id',
          name: 'AdminCallHistoryDetail',
          component: 'admin/call-history/detail',
          meta: {
            title: { zh_CN: '通话详情', en_US: 'Call Detail' },
            hideInMenu: true,
          },
        },
      ],
    });

    // Templates kept routable for later; hide from phase-1 demo sidebar
    menuList.push({
      path: '/admin/templates',
      component: 'LAYOUT',
      redirect: '/admin/templates/index',
      name: 'AdminTemplates',
      meta: {
        single: true,
        title: { zh_CN: 'Agent 模板', en_US: 'Agent Templates' },
        icon: 'root-list',
        orderNo: 2,
        hideInMenu: true,
      },
      children: [
        {
          path: 'index',
          name: 'AdminTemplatesIndex',
          component: 'admin/templates/index',
          meta: { title: { zh_CN: 'Agent 模板', en_US: 'Agent Templates' } },
        },
      ],
    });

    try {
      let list = filterMenusByPermission(userStore, menuList);
      if (role === 'admin') {
        list = list.filter((m: any) => m.path && m.path.startsWith('/admin'));
      } else if (role === 'user') {
        list = list.filter((m: any) => m.path && m.path.startsWith('/user'));
      }
      list = list.filter((menu: any) => menu.children && menu.children.length !== 0);
      resolve({ list });
    } catch (error) {
      console.error(error);
      reject({});
    }
  });
}

//@ts-ignore
function filterMenusByPermission(userStore, menus) {
  if (!Array.isArray(menus)) return [];

  return menus
    .map((menu) => {
      const newMenu = { ...menu, meta: { ...menu.meta } };
      if (typeof newMenu.meta.single !== 'boolean') {
        newMenu.meta.single = false;
      }
      if (Array.isArray(menu.children) && menu.children.length > 0) {
        newMenu.children = filterMenusByPermission(userStore, menu.children);
      } else {
        newMenu.children = [];
      }
      return newMenu;
    })
    .filter((menu) => {
      // keep hideInMenu items in route tree; MenuContent hides them in sidebar
      if (menu.children && menu.children.length === 0 && !menu.component) return false;
      return true;
    });
}
