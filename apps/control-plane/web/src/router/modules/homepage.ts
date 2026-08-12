import {DashboardIcon, AssignmentIcon, StarIcon, ListIcon} from 'tdesign-icons-vue-next';
import {shallowRef} from 'vue';
import Layout from '@/layouts/index.vue';

export default [
    // {
    //     path: '/take-leave',
    //     component: Layout,
    //     redirect: '/take-leave/list',
    //     name: 'honorArchive',
    //     meta: {
    //         single: true,
    //         title: {
    //             zh_CN: '荣誉归档',
    //             en_US: 'Honor Archive',
    //         },
    //         icon: shallowRef(StarIcon),
    //         orderNo: 0,
    //     },
    //     children: [
    //         {
    //             path: 'list',
    //             name: 'honorArchiveList',
    //             component: () => import('@/pages/take-leave/list.vue'),
    //             icon: shallowRef(ListIcon),
    //             meta: {
    //                 title: {
    //                     zh_CN: '归档列表',
    //                     en_US: 'Item list',
    //                 },
    //             },
    //         }
    //     ],
    // },
    // {
    //     path: '/user-manager',
    //     component: Layout,
    //     redirect: '/user-manager/list',
    //     name: 'userManager',
    //     meta: {
    //         title: {
    //             zh_CN: '用户管理',
    //             en_US: 'User management',
    //         },
    //         icon: shallowRef(AssignmentIcon),
    //         orderNo: 0,
    //     },
    //     children: [
    //         {
    //             path: 'list',
    //             name: 'userManagerList',
    //             component: () => import('@/pages/user-manager/list.vue'),
    //             meta: {
    //                 title: {
    //                     zh_CN: '用户列表',
    //                     en_US: 'User list',
    //                 },
    //             },
    //         }
    //     ],
    // },

    // {
    //     path: '/dashboard',
    //     component: Layout,
    //     redirect: '/dashboard/base',
    //     name: 'dashboard',
    //     meta: {
    //         title: {
    //             zh_CN: '仪表盘',
    //             en_US: 'Dashboard',
    //         },
    //         icon: shallowRef(DashboardIcon),
    //         orderNo: 0,
    //     },
    //     children: [
    //         {
    //             path: 'base',
    //             name: 'DashboardBase',
    //             component: () => import('@/pages/dashboard/base/index.vue'),
    //             meta: {
    //                 title: {
    //                     zh_CN: '概览仪表盘',
    //                     en_US: 'Overview',
    //                 },
    //             },
    //         },
    //         {
    //             path: 'detail',
    //             name: 'DashboardDetail',
    //             component: () => import('@/pages/dashboard/detail/index.vue'),
    //             meta: {
    //                 title: {
    //                     zh_CN: '统计报表',
    //                     en_US: 'Dashboard Detail',
    //                 },
    //             },
    //         },
    //     ],
    // },
];
