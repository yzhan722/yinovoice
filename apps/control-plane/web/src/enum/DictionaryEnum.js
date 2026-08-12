import { BASE_API } from '@/config/api';

export default {
  /** 管理员-获取 Voice 列表 */
  GET_VOICES: BASE_API + 'api/admin/dictionary/voices',
  /** 管理员-根据父编码查询列表 */
  LIST: BASE_API + 'api/admin/dictionary/list',
  /** 管理员-根据ID查询详情 */
  DETAIL: BASE_API + 'api/admin/dictionary/detail',
  /** 管理员-创建字典项 */
  CREATE: BASE_API + 'api/admin/dictionary/create',
  /** 管理员-更新字典项 */
  UPDATE: BASE_API + 'api/admin/dictionary/update',
  /** 管理员-删除字典项 */
  DELETE: BASE_API + 'api/admin/dictionary/delete',
};
