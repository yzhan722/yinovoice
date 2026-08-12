import UserKnowledgeBaseEnum from '@/enum/UserKnowledgeBaseEnum';
import $WRequest from '@/utils/request/WRequest';
import { shellMockEnabled } from '@/mocks/shell';
import { TenantKnowledgeMock } from './OpsServices';

const mock = new TenantKnowledgeMock();

/** Tenant — knowledge base (legacy: UserKnowledgeBaseService) */
export class TenantKnowledgeService {
  getList(param = {}) {
    if (shellMockEnabled()) {
      return mock.listMine(param);
    }
    return $WRequest.postNoAnimation(UserKnowledgeBaseEnum.LIST, { ...param });
  }

  uploadFile(file) {
    if (shellMockEnabled()) {
      return mock.upload(file);
    }
    const formData = new FormData();
    formData.append('file', file);
    return $WRequest.post(UserKnowledgeBaseEnum.UPLOAD, formData);
  }

  getAssociatedFiles() {
    if (shellMockEnabled()) {
      return mock.listAssociated();
    }
    return $WRequest.postNoAnimation(UserKnowledgeBaseEnum.ASSOCIATED_FILES, {});
  }

  updateStatus(fileId) {
    if (shellMockEnabled()) {
      return Promise.resolve({ fileId, filExtStatus: 'done' });
    }
    return $WRequest.postNoAnimation(UserKnowledgeBaseEnum.UPDATE_STATUS, { fileId });
  }
}
