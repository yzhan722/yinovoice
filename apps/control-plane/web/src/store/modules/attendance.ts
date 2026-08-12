import {defineStore} from 'pinia';

// 考勤状态枚举
export enum AttendanceStatus {
    PRESENT = 1,           // 正常出勤
    REST = -1,             // 公休
    // ABSENT = 0,            // 缺勤
    MATERNITY = 2,         // 产假
    MATERNITY_NORMAL = 3,  // 产假(顺产)
    MATERNITY_CESAREAN = 4, // 产假(剖腹)
    MARRIAGE = 5,          // 婚假
    ANNUAL = 6,            // 年休假
    BEREAVEMENT = 7,       // 丧假
    PARENTING = 8,         // 育儿假
    LONG_MATERNITY = 9,    // 长产假
    PERSONAL = 10,         // 事假
    SICK = 11,             // 病假
    WORK_INJURY = 12,      // 工伤假
    PATERNITY = 13,        // 陪产假
    STUDY = 14,            // 学习
    MEETING = 15,          // 会议
    BUSINESS_TRIP = 16,    // 出差
    ABSENTEEISM = 17,      // 旷工,
    VISIT_RELATIVES = 18, //探亲假
    NURSING_LEAVE = 19, // 护理假
    PARENTAL_LEAVE = 20 //陪护假
}

// 考勤状态配置
export interface AttendanceConfig {
    value: number;
    symbol: string;
    label: string;
    tooltip: string;
    color: 'success' | 'warning' | 'error' | 'default';
}

// 考勤状态配置映射
export const ATTENDANCE_CONFIG: Record<number, AttendanceConfig> = {
    [AttendanceStatus.PRESENT]: {
        value: 1,
        symbol: '√',
        label: '出勤',
        tooltip: '正常出勤',
        color: 'success'
    },
    [AttendanceStatus.REST]: {
        value: -1,
        symbol: '/',
        label: '公休',
        tooltip: '公休',
        color: 'default'
    },
    // [AttendanceStatus.ABSENT]: {
    //   value: 0,
    //   symbol: '0',
    //   label: '缺勤',
    //   tooltip: '缺勤',
    //   color: 'error'
    // },
    [AttendanceStatus.MATERNITY]: {
        value: 2,
        symbol: 'T',
        label: '产假',
        tooltip: '产假',
        color: 'warning'
    },
    [AttendanceStatus.MATERNITY_NORMAL]: {
        value: 3,
        symbol: 'TT',
        label: '产假(顺产)',
        tooltip: '产假(顺产)',
        color: 'warning'
    },
    [AttendanceStatus.MATERNITY_CESAREAN]: {
        value: 4,
        symbol: 'TTT',
        label: '产假(剖腹)',
        tooltip: '产假(剖腹)',
        color: 'warning'
    },
    [AttendanceStatus.MARRIAGE]: {
        value: 5,
        symbol: '◎',
        label: '婚假',
        tooltip: '婚假',
        color: 'warning'
    },
    [AttendanceStatus.ANNUAL]: {
        value: 6,
        symbol: '-',
        label: '年休假',
        tooltip: '年休假',
        color: 'warning'
    },
    [AttendanceStatus.BEREAVEMENT]: {
        value: 7,
        symbol: '○',
        label: '丧假',
        tooltip: '丧假',
        color: 'warning'
    },
    [AttendanceStatus.PARENTING]: {
        value: 8,
        symbol: '△△',
        label: '育儿假',
        tooltip: '育儿假',
        color: 'warning'
    },
    [AttendanceStatus.LONG_MATERNITY]: {
        value: 9,
        symbol: '→',
        label: '长产假',
        tooltip: '长产假',
        color: 'warning'
    },
    [AttendanceStatus.PERSONAL]: {
        value: 10,
        symbol: '=',
        label: '事假',
        tooltip: '事假',
        color: 'error'
    },
    [AttendanceStatus.SICK]: {
        value: 11,
        symbol: '▲',
        label: '病假',
        tooltip: '病假',
        color: 'error'
    },
    [AttendanceStatus.WORK_INJURY]: {
        value: 12,
        symbol: '+',
        label: '工伤假',
        tooltip: '工伤假',
        color: 'warning'
    },
    [AttendanceStatus.PATERNITY]: {
        value: 13,
        symbol: '#',
        label: '陪产假',
        tooltip: '陪产假',
        color: 'warning'
    },
    // [AttendanceStatus.STUDY]: {
    //     value: 14,
    //     symbol: '⊕',
    //     label: '学习',
    //     tooltip: '学习',
    //     color: 'warning'
    // },
    // [AttendanceStatus.MEETING]: {
    //     value: 15,
    //     symbol: '★',
    //     label: '会议',
    //     tooltip: '会议',
    //     color: 'warning'
    // },
    // [AttendanceStatus.BUSINESS_TRIP]: {
    //     value: 16,
    //     symbol: '☆',
    //     label: '出差',
    //     tooltip: '出差',
    //     color: 'warning'
    // },
    [AttendanceStatus.ABSENTEEISM]: {
        value: 17,
        symbol: '×',
        label: '旷工',
        tooltip: '旷工',
        color: 'error'
    },
    [AttendanceStatus.VISIT_RELATIVES]: {
        value: 18,
        symbol: '÷',
        label: '探亲假',
        tooltip: '探亲假',
        color: 'warning'
    },
    [AttendanceStatus.NURSING_LEAVE]: {
        value: 19,
        symbol: '∆',
        label: '护理假',
        tooltip: '护理假',
        color: 'warning'
    },
    [AttendanceStatus.PARENTAL_LEAVE]: {
        value: 20,
        symbol: '▼',
        label: '陪护假',
        tooltip: '陪护假',
        color: 'warning'
    }
};

// 统计列配置
export interface StatColumn {
    key: string;
    title: string;
    width: number;
    statusValues: number[];
}

// 统计列配置
export const STAT_COLUMNS: StatColumn[] = [
    {
        key: 'attendance',
        title: '出勤',
        width: 60,
        statusValues: [AttendanceStatus.PRESENT]
    },
    {
        key: 'maternityLeave',
        title: '产假',
        width: 60,
        statusValues: [AttendanceStatus.MATERNITY]
    },
    {
        key: 'maternityNaturalLeave',
        title: '产假(顺产)',
        width: 60,
        statusValues: [AttendanceStatus.MATERNITY_NORMAL]
    },
    {
        key: 'CesareanLeave',
        title: '产假(剖腹)',
        width: 60,
        statusValues: [AttendanceStatus.MATERNITY_CESAREAN]
    },
    {
        key: 'marriageLeave',
        title: '婚假',
        width: 60,
        statusValues: [AttendanceStatus.MARRIAGE]
    },
    {
        key: 'annualLeave',
        title: '年休',
        width: 60,
        statusValues: [AttendanceStatus.ANNUAL]
    },
    {
        key: 'familyVisit',
        title: '探亲',
        width: 60,
        statusValues: [AttendanceStatus.VISIT_RELATIVES] // 探亲假使用剖腹产假的值
    },
    {
        key: 'parentingLeave',
        title: '育儿假',
        width: 60,
        statusValues: [AttendanceStatus.PARENTING]
    },
    {
        key: 'nursingLeave',
        title: '护理假',
        width: 60,
        statusValues: [AttendanceStatus.NURSING_LEAVE]
    },
    {
        key: 'longMaternityLeave',
        title: '长产假',
        width: 60,
        statusValues: [AttendanceStatus.LONG_MATERNITY]
    },
    {
        key: 'personalLeave',
        title: '事假',
        width: 60,
        statusValues: [AttendanceStatus.PERSONAL]
    },
    {
        key: 'sickLeave',
        title: '病假',
        width: 60,
        statusValues: [AttendanceStatus.SICK]
    },
    {
        key: 'workInjury',
        title: '工伤',
        width: 60,
        statusValues: [AttendanceStatus.WORK_INJURY]
    },
    {
        key: 'paternityLeave',
        title: '陪产假',
        width: 60,
        statusValues: [AttendanceStatus.PATERNITY]
    },
    {
        key: 'bereavementLeave',
        title: '丧假',
        width: 60,
        statusValues: [AttendanceStatus.BEREAVEMENT]
    },
    {
        key: 'absenteeism',
        title: '旷工',
        width: 60,
        statusValues: [AttendanceStatus.ABSENTEEISM]
    }
];

export const useAttendanceStore = defineStore('attendance', {
    state: () => ({
        // 可以添加一些状态管理
    }),

    getters: {
        // 根据值获取考勤配置
        getAttendanceConfig: (state) => (value: number): AttendanceConfig | undefined => {
            return ATTENDANCE_CONFIG[value];
        },

        // 根据值获取符号
        getAttendanceSymbol: (state) => (value: number): string => {
            const config = ATTENDANCE_CONFIG[value];
            return config ? config.symbol : '';
        },

        // 根据值获取提示信息
        getAttendanceTooltip: (state) => (value: number): string => {
            const config = ATTENDANCE_CONFIG[value];
            return config ? config.tooltip : '';
        },

        // 根据值获取样式类
        getAttendanceClass: (state) => (value: number): string => {
            const config = ATTENDANCE_CONFIG[value];
            if (!config) return 'attendance-other';

            switch (config.color) {
                case 'success':
                    return 'attendance-present';
                case 'default':
                    return 'attendance-rest';
                case 'error':
                case 'warning':
                default:
                    return 'attendance-other';
            }
        },

        // 获取所有考勤配置
        getAllAttendanceConfigs: (state): AttendanceConfig[] => {
            return Object.values(ATTENDANCE_CONFIG);
        },

        // 获取统计列配置
        getStatColumns: (state): StatColumn[] => {
            return STAT_COLUMNS;
        }
    },

    actions: {
        // 计算统计数量
        calculateStatCount(row: any, statusValues: number[]): number {
            let count = 0;
            for (let i = 1; i <= 31; i++) {
                const dayValue = row[`day${i}`];
                if (statusValues.includes(dayValue)) {
                    count++;
                }
            }
            return count;
        }
    }
}); 