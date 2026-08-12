import AdminKnowledgeBaseEnum from '@/enum/AdminKnowledgeBaseEnum';
import $WRequest from '@/utils/request/WRequest';

/** Platform Operator — knowledge files (legacy: AdminKnowledgeBaseService) */
export class OperatorKnowledgeService {
  getList(param = {}) {
    return $WRequest.postNoAnimation(AdminKnowledgeBaseEnum.LIST, { ...param });
  }

  uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    return $WRequest.post(AdminKnowledgeBaseEnum.UPLOAD, formData);
  }

  /** @deprecated vendor sync */
  sync() {
    return $WRequest.post(AdminKnowledgeBaseEnum.SYNC, {});
  }

  getInstances(fileId) {
    return $WRequest.postNoAnimation(AdminKnowledgeBaseEnum.ASSISTANTS, { fileId });
  }

  getAssistants(fileId) {
    return this.getInstances(fileId);
  }

  updateStatus(fileId) {
    return $WRequest.postNoAnimation(AdminKnowledgeBaseEnum.UPDATE_STATUS, { fileId });
  }
}
