import {BASE_API} from "@/config/api";

export default {
    /**
     * 获取用户列表（分页）
     */
    GET_USER_LIST: BASE_API + 'api/admin/user/list',
    /**
     * 获取用户详情
     */
    GET_USER_DETAIL: BASE_API + 'api/admin/user/detail',
    /**
     * 更新用户信息
     */
    UPDATE_USER: BASE_API + 'api/admin/user/update',
    /**
     * 获取用户登录日志
     */
    GET_USER_LOGIN_LOGS: BASE_API + 'api/admin/user/loginLogs',
    /**
     * 检查账号是否存在
     */
    CHECK_ACCOUNT: BASE_API + 'api/admin/user/checkAccount',
    /**
     * 创建用户
     */
    CREATE_USER: BASE_API + 'api/admin/user/create',
    /**
     * 删除用户
     */
    DELETE_USER: BASE_API + 'api/admin/user/delete',
    /**
     * 更新用户密码
     */
    UPDATE_USER_PASSWORD: BASE_API + 'api/admin/user/updatePassword',
    /**
     * 更新用户头像
     */
    UPDATE_USER_AVATAR: BASE_API + 'api/admin/user/updateAvatar',
    /**
     * 获取用户操作日志
     */
    GET_USER_ACTION_LOGS: BASE_API + 'api/admin/user/actionLogs',
    /**
     * 分页查询用户登录日志
     */
    QUERY_LOGIN_LOGS_BY_PAGE: BASE_API + 'api/admin/user/loginLogs/page',
    /**
     * 分页查询用户操作日志
     */
    QUERY_ACTION_LOGS_BY_PAGE: BASE_API + 'api/admin/user/actionLogs/page',
};

