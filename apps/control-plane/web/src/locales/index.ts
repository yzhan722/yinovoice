import { DropdownOption } from 'tdesign-vue-next';
import { computed } from 'vue';
import { createI18n } from 'vue-i18n';

// 导入语言文件
const langModules = import.meta.glob('./lang/*/index.ts', { eager: true });

const langModuleMap = new Map<string, Object>();

export const langCode: Array<string> = [];

export const localeConfigKey = 'tdesign-starter-locale';

// 生成语言模块列表
const generateLangModuleMap = () => {
  const fullPaths = Object.keys(langModules);
  console.log(langModules, 'langModules');
  fullPaths.forEach((fullPath) => {
    const k = fullPath.replace('./lang', '');
    const startIndex = 1;
    const lastIndex = k.lastIndexOf('/');
    const code = k.substring(startIndex, lastIndex);
    langCode.push(code);
    console.log(langCode, 'langCode');
    langModuleMap.set(code, langModules[fullPath]);
  });
};

// 导出 Message
const importMessages = computed(() => {
  generateLangModuleMap();

  const message: Recordable = {};
  langModuleMap.forEach((value: any, key) => {
    message[key] = value.default;
  });
  return message;
});

// Default Chinese for China Regional Cell demo; user can still switch in UI.
const savedLocale = localStorage.getItem(localeConfigKey);
const defaultLocale = savedLocale || 'zh_CN';

export const i18n = createI18n({
  legacy: false,
  locale: defaultLocale,
  fallbackLocale: 'zh_CN',
  messages: importMessages.value,
  globalInjection: true,
});

if (!localStorage.getItem(localeConfigKey)) {
  localStorage.setItem(localeConfigKey, 'zh_CN');
}

export const langList = computed(() => {
  if (langModuleMap.size === 0) generateLangModuleMap();

  const list: DropdownOption[] = [];
  langModuleMap.forEach((value: any, key) => {
    list.push({
      content: value.default.lang,
      value: key,
    });
  });

  return list;
});

// @ts-ignore
export const { t } = i18n.global;

export default i18n;
