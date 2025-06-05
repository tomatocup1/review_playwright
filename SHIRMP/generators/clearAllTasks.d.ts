/**
 * clearAllTasks prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
/**
 * clearAllTasks prompt 參數介面
 */
export interface ClearAllTasksPromptParams {
    confirm?: boolean;
    success?: boolean;
    message?: string;
    backupFile?: string;
    isEmpty?: boolean;
}
/**
 * 獲取 clearAllTasks 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getClearAllTasksPrompt(params: ClearAllTasksPromptParams): string;
