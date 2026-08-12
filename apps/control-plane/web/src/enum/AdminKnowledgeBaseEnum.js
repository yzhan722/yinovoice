import { BASE_API } from '@/config/api';

export default {
  /** 管理员-文件列表（分页，支持文件名、状态筛选） */
  LIST: BASE_API + 'api/admin/knowledge-base/list',
  /** 管理员-上传文件并同步到 VAPI */
  UPLOAD: BASE_API + 'api/admin/knowledge-base/upload',
  /** 管理员-同步文件列表（从 VAPI 获取并更新本地） */
  SYNC: BASE_API + 'api/admin/knowledge-base/sync',
  /** 管理员-查看文件关联的 Assistant 列表 */
  ASSISTANTS: BASE_API + 'api/admin/knowledge-base/assistants',
  /** 管理员-更新单个文件状态 */
  UPDATE_STATUS: BASE_API + 'api/admin/knowledge-base/update-status',
};
