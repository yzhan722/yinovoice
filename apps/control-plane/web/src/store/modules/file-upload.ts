import {defineStore} from 'pinia';

export const useFileUploadStore = defineStore('file_upload', {
    state: () => ({
        selectedPath: '/',
    }),
    actions: {
        getCurrentPath(): Array<{ path: string; name: string }> {
            const defaultPath = [{
                path: '/',
                name: '全部文件'
            }];
            if (this.selectedPath === '/') {
                return defaultPath;
            }
            const isWindows = this.selectedPath.indexOf("\\") !== -1;
            const pathArr = isWindows ? this.selectedPath.split("\\") : this.selectedPath.split('/');
            const joinStr = isWindows ? "\\" : "/";
            const result = [...defaultPath];
            for (let i = 0; i < pathArr.length; i++) {
                let name = pathArr[i];
                if (!name) {
                    continue;
                }
                let path = pathArr.slice(0, i + 1).join(joinStr);
                result.push({path, name});
            }
            return result;
        },
        setPath(path: string) {
            this.selectedPath = path;
        }
    },
    persist: true
});
