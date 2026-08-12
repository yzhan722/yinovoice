import { BASE_API } from '@/config/api';

export default {
  /** 用户-文件列表（分页，仅当前用户上传的文件） */
  LIST: BASE_API + 'api/user/knowledge-base/list',
  /** 用户-上传文件并同步到 VAPI */
  UPLOAD: BASE_API + 'api/user/knowledge-base/upload',
  /** 用户-查看关联在 Assistant 的文件列表 */
  ASSOCIATED_FILES: BASE_API + 'api/user/knowledge-base/associated-files',
  /** 用户-更新单个文件状态 */
  UPDATE_STATUS: BASE_API + 'api/user/knowledge-base/update-status',
};
