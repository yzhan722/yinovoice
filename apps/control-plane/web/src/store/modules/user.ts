import {defineStore} from 'pinia';

import {usePermissionStore} from '@/store';
import type {UserInfo} from '@/types/interface';
//@ts-ignore
import {UserBasicService} from '@/api/UserBasicService';

const InitUserInfo: UserInfo = {
    name: '', // 用户名，用于展示在页面右上角头像处
    roles: [], // 前端权限模型使用 如果使用请配置modules/permission-fe.ts使用
};
const $UserBasicService = new UserBasicService();
export const useUserStore = defineStore('user', {
    state: () => ({
        token: '', // 兼容旧逻辑
        adminToken: '',
        adminTokenExpireTime: 0,
        adminInfo: { account: '' },
        userInfo: {...InitUserInfo},
        userToken: '',       // 用户端 token，与管理员隔离
        userTokenExpireTime: 0,
        userAccount: '',     // 当前登录用户账号（用户端）
    }),
    getters: {
        roles: (state) => {
            return state.userInfo?.roles;
        },
        // 获取管理员token（从sessionStorage读取）
        getAdminToken() {
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
        }
    },
    actions: {
        /** 用户端登录（/api/user/login），存 userToken */
        async userLogin(userInfo: Record<string, unknown>) {
            const account = userInfo.account as string;
            const password = userInfo.password as string;
            const result = await $UserBasicService.login({ account, password });
            const token = result?.token;
            const tokenExpireTime = result?.tokenExpireTime || (Date.now() + 24 * 60 * 60 * 1000);
            if (!token) throw new Error('登录返回缺少 token');
            sessionStorage.setItem('userToken', JSON.stringify({ token, expireTime: tokenExpireTime }));
            this.userToken = token;
            this.userTokenExpireTime = tokenExpireTime;
            this.userAccount = result?.account || account;
            if (result?.tenant_id) {
                sessionStorage.setItem('yinoTenantId', String(result.tenant_id));
            }
        },
        /** 用户端登出：清除 userToken */
        userLogout() {
            this.userToken = '';
            this.userTokenExpireTime = 0;
            this.userAccount = '';
            sessionStorage.removeItem('userToken');
            sessionStorage.removeItem('yinoTenantId');
        },
        /** 请求 profile 接口校验用户 token 是否有效，并拉取用户信息（供路由守卫用） */
        async getUserProfile() {
            const result = await $UserBasicService.getUserInfo({});
            if (result && (result.userNickname != null || result.userAccount != null)) {
                this.userAccount = result.userAccount || this.userAccount;
                this.userInfo = { ...this.userInfo, ...result, name: result.userNickname || result.userAccount };
            }
            return result;
        },
        async login(userInfo: Record<string, unknown>) {
            const loginAction = async (userInfo: Record<string, unknown>) => {
                const {account, password, loginModel} = userInfo;
                const result = await $UserBasicService.login({
                    account: account as string,
                    password: password as string,
                    ...(loginModel ? { loginModel: loginModel as string } : {}),
                });
                if (result?.token) {
                    return { code: 200, message: '登录成功', data: result.token };
                }
                return { code: 500, message: (result as any)?.message || '登录失败' };
            };
            const res = await loginAction(userInfo);
            if (res.code === 200) {
                this.token = res.data;
            } else {
                throw res;
            }
        },
        async getUserInfo() {
            const getRemoteUserInfo = async (token: string) => {
                const result = await $UserBasicService.getUserInfo({});
                return {
                    ...result,
                    code: 200,
                    name: (result as { useName?: string; userNickname?: string; userAccount?: string }).useName
                        || result.userNickname
                        || result.userAccount,
                    roles: ['all'], // 前端权限模型使用 如果使用请配置modules/permission-fe.ts使用
                };
            };
            this.userInfo = await getRemoteUserInfo(this.token);
        },
        async logout() {
            this.token = '';
            this.userInfo = {...InitUserInfo};
        },
        // 管理员登录
        async adminLogin(userInfo: Record<string, unknown>) {
            const loginAction = async (userInfo: Record<string, unknown>) => {
                // 登录请求流程
                const {account, password} = userInfo;
                //@ts-ignore
                const {AdminService} = await import('@/api/AdminService');
                const $AdminService = new AdminService();
                const result = await $AdminService.login({
                    account: account as string,
                    password: password as string,
                });
                // API层已经处理了成功/失败判断，这里直接使用返回的data
                const token = result.token;
                const expireTime = result.tokenExpireTime;
                // 保存到sessionStorage
                sessionStorage.setItem('adminToken', JSON.stringify({
                    token: token,
                    expireTime: expireTime || (Date.now() + 6 * 60 * 60 * 1000) // 默认6小时
                }));
                this.adminToken = token;
                this.adminTokenExpireTime = expireTime || (Date.now() + 6 * 60 * 60 * 1000);
                return token;
            };

            this.adminToken = await loginAction(userInfo);
        },
        // 获取管理员信息
        async getAdminInfo() {
            //@ts-ignore
            const {AdminService} = await import('@/api/AdminService');
            const $AdminService = new AdminService();
            const result = await $AdminService.getAdminInfo({});
            // 存储管理员信息
            this.adminInfo = {
                account: result.account || ''
            };
            return result;
        },
        // 管理员退出
        adminLogout() {
            this.adminToken = '';
            this.adminTokenExpireTime = 0;
            this.adminInfo = { account: '' };
            sessionStorage.removeItem('adminToken');
        },
        hasPermission(permission: Array<string> | string) {
            if (!this.userInfo?.permissions) return false;
            if (typeof permission === "string") {
                permission = [permission];
            }
            for (const item of permission) {
                if (!this.userInfo.permissions.includes(item)) {
                    return false;
                }
            }
            return true;
        },

        hasPermissionOr(permission: Array<string> | string) {
            if (!this.userInfo?.permissions || this.userInfo.permissions.length === 0) return false;
            if (!permission) return true; // 没传权限字段，默认无权限限制，直接通过
            if (typeof permission === "string") {
                permission = [permission];
            }
            // OR 逻辑，只要有一个权限匹配就返回 true
            return permission.some(p => this.userInfo.permissions.includes(p));
        }
    },
        persist: {
            afterRestore: () => {
                const permissionStore = usePermissionStore();
                permissionStore.initRoutes();
                try {
                    const adminTokenData = sessionStorage.getItem('adminToken');
                    if (adminTokenData) {
                        const data = JSON.parse(adminTokenData);
                        if (data.expireTime && data.expireTime > Date.now()) {
                            useUserStore().adminToken = data.token;
                            useUserStore().adminTokenExpireTime = data.expireTime;
                        }
                    }
                    const userTokenData = sessionStorage.getItem('userToken');
                    if (userTokenData) {
                        const data = JSON.parse(userTokenData);
                        if (data.expireTime && data.expireTime > Date.now()) {
                            useUserStore().userToken = data.token;
                            useUserStore().userTokenExpireTime = data.expireTime;
                        }
                    }
                } catch (e) {
                    console.error('恢复 token 失败', e);
                }
            },
            key: 'user',
            paths: ['token'],
        },
});
