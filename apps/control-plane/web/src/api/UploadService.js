import UploadEnum from "@/enum/UploadEnum";
import $WRequest from "@/utils/request/WRequest";

export class UploadService {
    /**
     * 上传图片
     */
    uploadImage(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const requestUrl = UploadEnum.UPLOAD_IMAGE;
        return $WRequest.request(requestUrl, formData, {
            'Content-Type': 'multipart/form-data'
        }, "POST", true, false).then(res => {
            return res;
        })
    }

    /**
     * 上传文件
     */
    uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const requestUrl = UploadEnum.UPLOAD_FILE;
        return $WRequest.request(requestUrl, formData, {
            'Content-Type': 'multipart/form-data'
        }, "POST", true, false).then(res => {
            return res;
        })
    }
}