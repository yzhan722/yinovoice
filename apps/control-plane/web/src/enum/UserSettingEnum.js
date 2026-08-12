import {BASE_API} from "@/config/api";

export default {
    /**
     * 获取用户列表
     */
    GET_USER_LIST: BASE_API + 'userSetting/getUserList',
    /**
     * 新增用户
     */
    ADD_USER: BASE_API + 'userSetting/addUser',
    /**
     * 编辑用户
     */
    UPDATE_USER: BASE_API + 'userSetting/updateUser',
    GET_TREE: BASE_API + 'userSetting/getTree',
    /**
     * 批量导入用户
     */
    BATCH_IMPORT_USER: BASE_API + 'userSetting/batchImportUser',
    /**
     * 刷新用户权限
     */
    REFRESH_USER_PERMISSION: BASE_API + 'userSetting/refreshUserPermission',
    /**
     * 更新小组信息
     */
    UPDATE_GROUP: BASE_API + 'userSetting/updateGroup',
    /**
     * 更新科室信息
     */
    UPDATE_DEPT: BASE_API + 'userSetting/updateDept',
}; 