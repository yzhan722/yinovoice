import {BASE_API, BASE_PYTHON_API} from "@/config/api";

/** 用户端接口（与管理员 /api/admin/* 隔离） */
export default {
    /**
     * 用户登录
     */
    LOGIN: BASE_API + 'api/user/login',
    /**
     * 获取用户信息（需用户 Token）
     */
    GET_USER_INFO: BASE_API + 'api/user/profile',
    /**
     * 退出登陆（前端清除 token 即可，无单独接口可留空或后续扩展）
     */
    LOGOUT: BASE_API + 'api/user/logout',
    /**
     * 获取python服务accessToken
     */
    GET_ACCESS_TOKEN: BASE_PYTHON_API + 'getAccessToken',
}