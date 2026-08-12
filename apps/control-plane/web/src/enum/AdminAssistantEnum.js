import {BASE_API} from "@/config/api";

export default {
    /**
     * 获取AI助手列表（分页）
     */
    GET_ASSISTANT_LIST: BASE_API + 'api/admin/assistant/list',
    /**
     * 获取AI助手详情
     */
    GET_ASSISTANT_DETAIL: BASE_API + 'api/admin/assistant/detail',
    /**
     * 更新AI助手信息
     */
    UPDATE_ASSISTANT: BASE_API + 'api/admin/assistant/update',
    /**
     * 同步助手数据
     */
    SYNC_ASSISTANTS: BASE_API + 'api/admin/assistant/sync',
    /**
     * 分配助手给用户
     */
    ASSIGN_ASSISTANT: BASE_API + 'api/admin/assistant/assign',
    /**
     * 搜索用户
     */
    SEARCH_USERS: BASE_API + 'api/admin/assistant/searchUsers',
};