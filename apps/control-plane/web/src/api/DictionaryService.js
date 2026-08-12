import DictionaryEnum from '@/enum/DictionaryEnum';
import $WRequest from '@/utils/request/WRequest';

export class DictionaryService {
  /** 获取 Voice 列表 */
  getVoices() {
    return $WRequest.postNoAnimation(DictionaryEnum.GET_VOICES, {});
  }

  /** 根据父编码查询列表 */
  getList(param = {}) {
    return $WRequest.postNoAnimation(DictionaryEnum.LIST, { ...param });
  }

  /** 根据ID查询详情 */
  getDetail(diyId) {
    return $WRequest.postNoAnimation(DictionaryEnum.DETAIL, { diyId });
  }

  /** 创建字典项 */
  create(param) {
    return $WRequest.post(DictionaryEnum.CREATE, { ...param });
  }

  /** 更新字典项 */
  update(param) {
    return $WRequest.post(DictionaryEnum.UPDATE, { ...param });
  }

  /** 删除字典项 */
  delete(diyId) {
    return $WRequest.post(DictionaryEnum.DELETE, { diyId });
  }
}
