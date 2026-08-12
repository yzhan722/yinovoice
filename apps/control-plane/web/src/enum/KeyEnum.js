import {BASE_API} from "@/config/api";

export default {
    /**
     * 创建密钥
     */
    CREATE_KEY: BASE_API + 'api/admin/key/create',
    /**
     * 更新密钥
     */
    UPDATE_KEY: BASE_API + 'api/admin/key/update',
    /**
     * 获取密钥列表（分页）
     */
    GET_KEY_LIST: BASE_API + 'api/admin/key/list',
    /**
     * 获取密钥详情
     */
    GET_KEY_DETAIL: BASE_API + 'api/admin/key/detail',
    /**
     * 解绑密钥
     */
    UNBIND_KEY: BASE_API + 'api/admin/key/unbind',
};

