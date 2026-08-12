import UserDictionaryEnum from '@/enum/UserDictionaryEnum';
import $WRequest from '@/utils/request/WRequest';
import { shellMockEnabled } from '@/mocks/shell';

export class UserDictionaryService {
  /** 获取 Voice 列表 */
  getVoices() {
    if (shellMockEnabled()) {
      return Promise.resolve([
        { diyName: 'Sarah', diyCode: 'sarah' },
        { diyName: 'Lily', diyCode: 'lily' },
        { diyName: 'Hana', diyCode: 'hana' },
      ]);
    }
    return $WRequest.postNoAnimation(UserDictionaryEnum.GET_VOICES, {});
  }
}
