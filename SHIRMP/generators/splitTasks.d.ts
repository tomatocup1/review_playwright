/**
 * splitTasks prompt 生成器
 * 負責將模板和參數組合成最終的 prompt
 */
import { Task } from "../../types/index.js";
/**
 * splitTasks prompt 參數介面
 */
export interface SplitTasksPromptParams {
    updateMode: string;
    createdTasks: Task[];
    allTasks: Task[];
}
/**
 * 獲取 splitTasks 的完整 prompt
 * @param params prompt 參數
 * @returns 生成的 prompt
 */
export declare function getSplitTasksPrompt(params: SplitTasksPromptParams): string;
