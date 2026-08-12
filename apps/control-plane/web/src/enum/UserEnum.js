import {BASE_API} from "@/config/api";

export default {
    /**
     * 获取用户信息
     */
    GET_USER_INFO: BASE_API + 'api/user/info',
    /**
     * 获取用户个人资料
     */
    GET_USER_PROFILE: BASE_API + 'api/user/profile',
    /**
     * 更新用户个人资料
     */
    UPDATE_USER_PROFILE: BASE_API + 'api/user/updateProfile',
    /**
     * 修改密码
     */
    CHANGE_PASSWORD: BASE_API + 'api/user/changePassword',
    /** 用户-当前用户拥有的助手选项（attId、attVendorId、attName） */
    ASSISTANT_OPTIONS: BASE_API + 'api/user/assistant-options',
    /** 用户-助手详情（仅归属校验通过时返回） */
    ASSISTANT_DETAIL: BASE_API + 'api/user/assistant/detail',
    /** 用户-更新助手配置 */
    ASSISTANT_UPDATE: BASE_API + 'api/user/assistant/update',
    /** 用户-通话记录分页 */
    CALL_HISTORY_LIST: BASE_API + 'api/user/call-history/list',
    /** 用户-手动同步通话 */
    CALL_HISTORY_SYNC: BASE_API + 'api/user/call-history/sync',
    /** 用户-通话详情（含 messages，已排除 system） */
    CALL_HISTORY_DETAIL: BASE_API + 'api/user/call-history/detail',
};